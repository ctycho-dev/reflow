# jobs/checker/job.py
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.database.connection import DatabaseManager
from app.domain.campaign.repo import CampaignRepository
from app.domain.enrollment.repo import EnrollmentRepository
from app.domain.transfer.repo import TransferRepository

logger = get_logger(__name__)

GRACE_PERIOD_HOURS = 12
BATCH_SIZE = 500


class CheckerJob:
    """
    Re-aggregates total_volume for all enrollments whose campaign window
    is open (with grace). Sets qualified_at when threshold is crossed.

    One job tick processes every eligible enrollment in cursor-paginated
    batches. Per-row transactions: a failure on one enrollment doesn't
    block the rest of the batch.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self.enrollment_repo = EnrollmentRepository()
        self.campaign_repo = CampaignRepository()
        self.transfer_repo = TransferRepository()

    async def run(self) -> None:
        started = datetime.now(timezone.utc)
        grace_cutoff = started - timedelta(hours=GRACE_PERIOD_HOURS)
        after_id = 0
        total_seen = 0
        total_updated = 0
        total_newly_qualified = 0
        errors = 0

        while True:
            # Read a batch of candidate enrollments. Short-lived session.
            async with self.db.session_scope() as session:
                batch = await self.enrollment_repo.list_active_for_recompute(
                    session,
                    after_id=after_id,
                    grace_cutoff=grace_cutoff,
                    limit=BATCH_SIZE,
                )

            if not batch:
                break

            for enrollment in batch:
                total_seen += 1
                try:
                    updated, newly_qualified = await self._process_one(
                        enrollment_id=enrollment.id
                    )
                    if updated:
                        total_updated += 1
                    if newly_qualified:
                        total_newly_qualified += 1
                except Exception as e:
                    errors += 1
                    logger.exception(
                        "checker: failed to process enrollment id=%s: %s",
                        enrollment.id, e,
                    )

            after_id = batch[-1].id

        duration = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "checker tick complete: seen=%d updated=%d newly_qualified=%d errors=%d duration=%.2fs",
            total_seen, total_updated, total_newly_qualified, errors, duration,
        )

    async def _process_one(self, *, enrollment_id: int) -> tuple[bool, bool]:
        """
        Per-enrollment transaction. Returns (volume_changed, newly_qualified).

        Re-reads the enrollment + campaign inside its own session so we don't
        hold stale references across batches.
        """
        async with self.db.session_scope() as session:
            enrollment = await self.enrollment_repo.get_by_id(session, enrollment_id)
            campaign = await self.campaign_repo.get_by_id(session, enrollment.campaign_id)

            new_volume = await self.transfer_repo.sum_volume_for_wallet(
                session,
                chain_id=campaign.chain_id,
                token_address=campaign.token_address,
                wallet_address=enrollment.wallet_address,
                start_ts=campaign.starts_at,
                end_ts=campaign.ends_at,
                target_contract_address=campaign.target_contract_address,
            )

            old_volume = enrollment.total_volume
            already_qualified = enrollment.qualified_at is not None
            crosses_threshold = (
                not already_qualified
                and new_volume >= campaign.min_total_volume
            )

            if new_volume == old_volume and not crosses_threshold:
                return (False, False)

            qualified_at = (
                enrollment.qualified_at
                if already_qualified
                else (datetime.now(timezone.utc) if crosses_threshold else None)
            )

            await self.enrollment_repo.set_volume_and_qualified(
                session,
                enrollment_id=enrollment.id,
                total_volume=new_volume,
                qualified_at=qualified_at,
            )

            await session.commit()

            if crosses_threshold:
                logger.info(
                    "checker: wallet=%s campaign=%s newly qualified at volume=%s threshold=%s",
                    enrollment.wallet_address,
                    enrollment.campaign_id,
                    format(new_volume, "f"),
                    format(campaign.min_total_volume, "f"),
                )

            return (new_volume != old_volume, crosses_threshold)
