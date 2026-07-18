# app/domain/campaign/finalizer_repo.py
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.campaign.model import Campaign, MerkleRoot, RewardClaim
from app.domain.enrollment.model import Enrollment
from app.enums.enums import MerkleRootStatus


class FinalizerRepository:
    """Persistence for campaign finalization (merkle_roots + reward_claims).
    Stateless — session passed per method, matching the rest of the codebase."""

    async def get_campaign(self, session: AsyncSession, campaign_id: int) -> Campaign | None:
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def get_existing_root(self, session: AsyncSession, campaign_id: int) -> MerkleRoot | None:
        """Idempotency guard — a campaign is finalized at most once."""
        result = await session.execute(
            select(MerkleRoot).where(MerkleRoot.campaign_id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def get_qualified_winners(
        self, session: AsyncSession, campaign_id: int
    ) -> list[tuple[str, Decimal]]:
        """Qualified enrollments as (wallet_address, total_volume), sorted by
        address for deterministic tree construction."""
        result = await session.execute(
            select(Enrollment.wallet_address, Enrollment.total_volume)
            .where(
                Enrollment.campaign_id == campaign_id,
                Enrollment.qualified_at.is_not(None),
            )
            .order_by(Enrollment.wallet_address.asc())
        )
        return [(row.wallet_address, row.total_volume) for row in result.all()]

    async def persist_finalization(
        self,
        session: AsyncSession,
        *,
        campaign_id: int,
        chain_id: int,
        root_hash: bytes,
        total_amount: Decimal,
        winner_count: int,
        claims: list[dict],
    ) -> MerkleRoot:
        """Write merkle_roots + reward_claims. Caller owns the transaction
        (session_scope does not auto-commit); this only stages writes."""
        root = MerkleRoot(
            campaign_id=campaign_id,
            chain_id=chain_id,
            root_hash=root_hash,
            total_amount=total_amount,
            winner_count=winner_count,
            status=MerkleRootStatus.pending.value,
        )
        session.add(root)

        for c in claims:
            session.add(
                RewardClaim(
                    campaign_id=campaign_id,
                    wallet_address=c["wallet_address"],
                    amount=c["amount"],
                    leaf_index=c["leaf_index"],
                    proof=c["proof"],
                )
            )

        await session.flush()  # surface IntegrityError within caller's tx
        return root

    async def persist_no_winners(
        self, session: AsyncSession, *, campaign_id: int, chain_id: int
    ) -> MerkleRoot:
        """Record finalization with zero qualified winners."""
        root = MerkleRoot(
            campaign_id=campaign_id,
            chain_id=chain_id,
            root_hash=b"\x00" * 32,  # no real root; sentinel
            total_amount=Decimal(0),
            winner_count=0,
            status=MerkleRootStatus.no_winners.value,
        )
        session.add(root)
        await session.flush()
        return root

    async def get_claim(
        self, session: AsyncSession, campaign_id: int, wallet_address: str
    ) -> RewardClaim | None:
        result = await session.execute(
            select(RewardClaim).where(
                RewardClaim.campaign_id == campaign_id,
                RewardClaim.wallet_address == wallet_address.lower(),
            )
        )
        return result.scalar_one_or_none()