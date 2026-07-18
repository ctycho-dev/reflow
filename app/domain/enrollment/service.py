# app/domain/enrollment/service.py
from datetime import datetime, timezone
from decimal import Decimal
from datetime import timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.domain.campaign.repo import CampaignRepository
from app.domain.campaign.schema import CampaignOutSchema
from app.domain.enrollment.repo import EnrollmentRepository
from app.domain.enrollment.schema import (
    EnrollmentOutSchema,
    LeaderboardEntrySchema,
    CampaignEligibilitySchema,
    WalletEligibilitySchema,
)
from app.domain.transfer.repo import TransferRepository
from app.domain.wallet.repo import WalletRepository
from app.exceptions.exceptions import ValidationError
from app.core.constants import GRACE_PERIOD_HOURS


logger = get_logger(__name__)


class EnrollmentService:
    def __init__(
        self,
        repo: EnrollmentRepository,
        campaign_repo: CampaignRepository,
        wallet_repo: WalletRepository,
        transfer_repo: TransferRepository,
    ):
        self.repo = repo
        self.campaign_repo = campaign_repo
        self.wallet_repo = wallet_repo
        self.transfer_repo = transfer_repo

    # -----------------------------------------------------------------
    # Public: enroll a wallet in a campaign
    # -----------------------------------------------------------------

    async def enroll(
        self,
        session: AsyncSession,
        *,
        campaign_id: int,
        wallet_chain_id: int,
        wallet_address: str,
    ) -> EnrollmentOutSchema:
        """
        Atomically enroll a wallet in a campaign.

        Steps (all-or-nothing within one transaction):
          1. Load campaign config; verify it's joinable (exists, not expired, not future)
          2. Reject duplicate enrollment (409)
          3. Reserve a slot atomically — fails if campaign is full (409)
          4. Upsert wallet row (FK precondition)
          5. Insert enrollment row
          6. Aggregate historical transfer volume in the campaign window
          7. Set qualified_at if volume >= threshold
          8. Commit

        Any failure rolls back, including the reserved slot.
        """
        # 1. Campaign exists + is joinable
        campaign = await self.campaign_repo.get_by_id(session, campaign_id)

        now = datetime.now(timezone.utc)
        if now < campaign.starts_at:
            raise ValidationError(
                f"Campaign {campaign_id} has not started yet"
            )
        if now > campaign.ends_at:
            raise ValidationError(
                f"Campaign {campaign_id} has already ended"
            )

        # 2. Reject duplicate before doing any mutating work
        existing = await self.repo.get_by_wallet_campaign(
            session,
            wallet_chain_id=wallet_chain_id,
            wallet_address=wallet_address,
            campaign_id=campaign_id,
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Wallet is already enrolled in this campaign",
            )

        # 3. Reserve the slot atomically. Failure = campaign is full.
        slot_reserved = await self.campaign_repo.try_increment_enrolled_count(
            session, campaign_id
        )
        if not slot_reserved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Campaign is full",
            )

        # 4. Upsert wallet (FK precondition for enrollment row)
        await self.wallet_repo.upsert(
            session,
            chain_id=wallet_chain_id,
            address=wallet_address,
        )

        # 5. Create the enrollment row (volume + qualified_at filled in step 7)
        enrollment = await self.repo.create(
            session,
            data={
                "wallet_chain_id": wallet_chain_id,
                "wallet_address": wallet_address,
                "campaign_id": campaign_id,
                # total_volume defaults to 0 via server_default
                # qualified_at defaults to NULL
            },
        )

        # 6. Aggregate historical volume in the campaign window
        total_volume = await self.transfer_repo.sum_volume_for_wallet(
            session,
            chain_id=campaign.chain_id,
            token_address=campaign.token_address,
            wallet_address=wallet_address,
            start_ts=campaign.starts_at,
            end_ts=campaign.ends_at,
            target_contract_address=campaign.target_contract_address,
        )

        # 7. Set qualified_at if threshold met
        qualified_at = now if total_volume >= campaign.min_total_volume else None
        await self.repo.set_volume_and_qualified(
            session,
            enrollment_id=enrollment.id,
            total_volume=total_volume,
            qualified_at=qualified_at,
        )

        # 8. Commit and reload for the response
        await session.commit()
        await session.refresh(enrollment)

        logger.info(
            "enrollment created id=%s wallet=%s campaign=%s volume=%s qualified=%s",
            enrollment.id,
            wallet_address,
            campaign_id,
            format(total_volume, "f"),
            qualified_at is not None,
        )

        return EnrollmentOutSchema.model_validate(
            enrollment,
            from_attributes=True
        )

    async def get_leaderboard(
        self,
        session: AsyncSession,
        *,
        campaign_id: int,
        limit: int = 100,
    ) -> list[LeaderboardEntrySchema]:
        """
        Top wallets in a campaign by total volume. Verifies campaign exists
        (404 if not). Returns up to `limit` entries, rank-numbered from 1.
        """
        await self.campaign_repo.get_by_id(session, campaign_id)

        enrollments = await self.repo.leaderboard(
            session, campaign_id=campaign_id, limit=limit,
        )

        return [
            LeaderboardEntrySchema(
                rank=i + 1,
                wallet_address=e.wallet_address,
                total_volume=e.total_volume,
                qualified=e.qualified_at is not None,
            )
            for i, e in enumerate(enrollments)
        ]

    async def get_wallet_eligibility(
        self,
        session: AsyncSession,
        *,
        chain_id: int,
        wallet_address: str,
    ) -> WalletEligibilitySchema:
        """
        Cross-campaign eligibility snapshot for a wallet.

        Includes active campaigns + recently-ended campaigns within the
        grace period (so users can see their final state on just-closed
        campaigns).
        """
        wallet_address = wallet_address.lower()
        now = datetime.now(timezone.utc)

        # Active campaigns on this chain
        active = await self.campaign_repo.list_active(session, chain_id=chain_id)

        # Recently-ended (within grace) — filter list_ended() by ends_at threshold
        ended = await self.campaign_repo.list_ended(session, chain_id=chain_id, limit=100)
        grace_cutoff = now - timedelta(hours=GRACE_PERIOD_HOURS)
        recently_ended = [c for c in ended if c.ends_at >= grace_cutoff]

        all_campaigns = active + recently_ended
        campaign_ids = [c.id for c in all_campaigns]

        # Bulk-fetch enrollments for this wallet across those campaigns
        enrollments = await self.repo.get_for_wallet_in_campaigns(
            session,
            wallet_chain_id=chain_id,
            wallet_address=wallet_address,
            campaign_ids=campaign_ids,
        )

        # Compose the per-campaign view
        rows: list[CampaignEligibilitySchema] = []
        for campaign in all_campaigns:
            enrollment = enrollments.get(campaign.id)
            total_volume = enrollment.total_volume if enrollment else Decimal(0)
            qualified = enrollment is not None and enrollment.qualified_at is not None
            progress = (
                float(min(total_volume / campaign.min_total_volume, Decimal(1)))
                if campaign.min_total_volume > 0
                else 0.0
            )
            rows.append(CampaignEligibilitySchema(
                campaign=CampaignOutSchema.model_validate(campaign, from_attributes=True),
                enrolled=enrollment is not None,
                qualified=qualified,
                total_volume=total_volume,
                progress=progress,
            ))

        return WalletEligibilitySchema(
            wallet_address=wallet_address,
            chain_id=chain_id,
            campaigns=rows,
        )