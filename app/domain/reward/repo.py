# app/domain/reward/repo.py
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.base_repository import BaseRepository
from app.domain.campaign.model import RewardClaim
from app.exceptions.exceptions import DatabaseError


class RewardClaimRepository(BaseRepository[RewardClaim]):
    def __init__(self) -> None:
        super().__init__(RewardClaim)

    async def mark_claimed(
        self,
        session: AsyncSession,
        *,
        campaign_id: int,
        wallet_address: str,
        claimed_ts: int,
        claim_tx_hash: bytes,
    ) -> bool:
        """
        Mirror an on-chain Claimed event. Idempotent: only flips rows where
        claimed_at IS NULL, so backfill replay is harmless.
        Returns True if a row was updated.
        """
        try:
            stmt = (
                update(RewardClaim)
                .where(
                    RewardClaim.campaign_id == campaign_id,
                    RewardClaim.wallet_address == wallet_address,
                    RewardClaim.claimed_at.is_(None),
                )
                .values(
                    claimed_at=datetime.fromtimestamp(claimed_ts, tz=timezone.utc),
                    claim_tx_hash=claim_tx_hash,
                )
            )
            result = await session.execute(stmt)
            return result.rowcount > 0
        except Exception as e:
            raise DatabaseError(
                f"Failed to mark claim for campaign {campaign_id} "
                f"wallet {wallet_address}: {e}"
            ) from e
