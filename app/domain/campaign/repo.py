# app/domain/campaign/repo.py
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.base_repository import BaseRepository
from app.domain.campaign.model import Campaign


class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self):
        super().__init__(Campaign)

    async def list_by_chain(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> Sequence[Campaign]:
        stmt = select(Campaign).order_by(Campaign.starts_at.desc())
        if chain_id is not None:
            stmt = stmt.where(Campaign.chain_id == chain_id)
        return (await session.execute(stmt)).scalars().all()

    async def list_active(
        self,
        session: AsyncSession,
        chain_id: int | None = None,
    ) -> list[Campaign]:
        """Active = starts_at <= now <= ends_at. Ordered newest-first."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Campaign)
            .where(
                and_(
                    Campaign.starts_at <= now,
                    Campaign.ends_at >= now,
                )
            )
            .order_by(Campaign.starts_at.desc())
        )
        if chain_id is not None:
            stmt = stmt.where(Campaign.chain_id == chain_id)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def list_ended(
        self,
        session: AsyncSession,
        chain_id: int | None = None,
        limit: int = 50,
    ) -> list[Campaign]:
        """Campaigns whose window has closed. Most recent first."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Campaign)
            .where(Campaign.ends_at < now)
            .order_by(Campaign.ends_at.desc())
            .limit(limit)
        )
        if chain_id is not None:
            stmt = stmt.where(Campaign.chain_id == chain_id)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id_for_update(
        self,
        session: AsyncSession,
        campaign_id: int,
    ) -> Campaign | None:
        """
        Row-level lock. Use inside the enroll transaction when you need
        to read campaign config (e.g. min_total_volume) consistently with
        the enrollment write. Concurrent enrollments serialize on this row.
        """
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id).with_for_update()
        )
        return result.scalar_one_or_none()

    # -----------------------------------------------------------------
    # Atomic cap check — the core of safe concurrent enrollment
    # -----------------------------------------------------------------

    async def try_increment_enrolled_count(
        self,
        session: AsyncSession,
        campaign_id: int,
    ) -> bool:
        """
        Atomically reserve a slot. Returns True if a slot was claimed,
        False if the campaign is already full.

        Single statement → no race condition, no explicit locking.
        Two concurrent calls cannot both succeed: Postgres serializes the
        UPDATE on the row, the second one sees the new enrolled_count and
        either succeeds (slot still available) or returns 0 rows (full).

        The campaign-level CHECK constraint (enrolled_count <= max_recipients)
        is a belt-and-braces backstop: even if this method is bypassed, the
        DB will refuse to exceed the cap.
        """
        stmt = (
            update(Campaign)
            .where(
                and_(
                    Campaign.id == campaign_id,
                    Campaign.enrolled_count < Campaign.max_recipients,
                )
            )
            .values(enrolled_count=Campaign.enrolled_count + 1)
            .returning(Campaign.id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None