# app/domain/campaign/service.py
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.domain.campaign.repo import CampaignRepository
from app.domain.campaign.schema import (
    CampaignCreateSchema,
    CampaignOutSchema,
)
from app.domain.contract.repo import ContractRepository
from app.domain.token.repo import TokenRepository

logger = get_logger(__name__)


class CampaignService:
    def __init__(
        self,
        repo: CampaignRepository,
        token_repo: TokenRepository,
        contract_repo: ContractRepository,
    ):
        self.repo = repo
        self.token_repo = token_repo
        self.contract_repo = contract_repo

    # -----------------------------------------------------------------
    # Admin: create
    # -----------------------------------------------------------------

    async def create_campaign(
        self,
        session: AsyncSession,
        payload: CampaignCreateSchema,
    ) -> CampaignOutSchema:
        now = datetime.now(timezone.utc)
        starts_at = payload.starts_at or now
        ends_at = starts_at + timedelta(days=payload.duration_days)

        if ends_at <= now:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Campaign end time must be in the future",
            )

        # FK guards. The DB FKs would also catch these, but a 422 with a
        # readable message is better DX than a driver-level error.
        await self._assert_token_exists(
            session, chain_id=payload.chain_id, address=payload.token_address,
        )
        if payload.target_contract_address:
            await self._assert_contract_exists(
                session,
                chain_id=payload.chain_id,
                address=payload.target_contract_address,
            )

        # Build the dict the model constructor expects. Address normalization
        # already happened in the schema validator.
        create_data = {
            "name": payload.name,
            "description": payload.description,
            "chain_id": payload.chain_id,
            "token_address": payload.token_address,
            "target_contract_address": payload.target_contract_address,
            "min_total_volume": payload.min_total_volume,
            "reward_amount": payload.reward_amount,
            "duration_days": payload.duration_days,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "max_recipients": payload.max_recipients,
            # enrolled_count defaults to 0 via server_default
        }
        campaign = await self.repo.create(session, data=create_data)
        await session.commit()
        await session.refresh(campaign)
        logger.info(
            "campaign created id=%s name=%s chain=%s token=%s cap=%s window=%s..%s",
            campaign.id,
            campaign.name,
            campaign.chain_id,
            campaign.token_address,
            campaign.max_recipients,
            campaign.starts_at.isoformat(),
            campaign.ends_at.isoformat(),
        )

        return CampaignOutSchema.model_validate(campaign, from_attributes=True)

    async def list_by_chain(
        self,
        session: AsyncSession,
        chain_id: int | None = None,
    ) -> list[CampaignOutSchema]:
        campaigns = await self.repo.list_by_chain(session, chain_id=chain_id)
        return [
            CampaignOutSchema.model_validate(c, from_attributes=True)
            for c in campaigns
        ]

    # -----------------------------------------------------------------
    # Public: get by id
    # -----------------------------------------------------------------

    async def get_campaign(
        self,
        session: AsyncSession,
        campaign_id: int,
    ) -> CampaignOutSchema:
        campaign = await self.repo.get_by_id(session, campaign_id)
        return CampaignOutSchema.model_validate(campaign, from_attributes=True)

    async def delete_campaign(
        self,
        session: AsyncSession,
        campaign_id: int,
    ) -> None:
        await self.repo.delete_by_id(session, campaign_id)
        logger.info("campaign deleted id=%s", campaign_id)

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    async def _assert_token_exists(
        self,
        session: AsyncSession,
        *,
        chain_id: int,
        address: str,
    ) -> None:
        # NB: assumes TokenRepository.exists(session, *, chain_id, address) -> bool.
        # If your token repo doesn't have it yet, add as:
        #   stmt = select(Token.address).where(...).limit(1)
        exists = await self.token_repo.exists(
            session, chain_id=chain_id, address=address
        )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Token {address} not indexed on chain {chain_id}",
            )

    async def _assert_contract_exists(
        self,
        session: AsyncSession,
        *,
        chain_id: int,
        address: str,
    ) -> None:
        # NB: assumes ContractRepository.exists(session, *, chain_id, address) -> bool.
        exists = await self.contract_repo.exists(
            session, chain_id=chain_id, address=address
        )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Target contract {address} not registered "
                    f"on chain {chain_id}"
                ),
            )
