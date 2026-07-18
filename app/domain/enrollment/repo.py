# app/domain/enrollment/repository.py
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence
from sqlalchemy import and_, select, update, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.base_repository import BaseRepository
from app.domain.enrollment.model import Enrollment
from app.domain.campaign.model import Campaign
from app.exceptions.exceptions import DatabaseError


class EnrollmentRepository(BaseRepository[Enrollment]):
    def __init__(self) -> None:
        super().__init__(Enrollment)

    async def get_by_wallet_campaign(
        self,
        session: AsyncSession,
        *,
        wallet_chain_id: int,
        wallet_address: str,
        campaign_id: int,
    ) -> Enrollment | None:
        try:
            stmt = select(Enrollment).where(
                and_(
                    Enrollment.wallet_chain_id == wallet_chain_id,
                    Enrollment.wallet_address == wallet_address,
                    Enrollment.campaign_id == campaign_id,
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(
                f"Failed to look up enrollment for wallet {wallet_address}: {e}"
            ) from e

    async def set_volume_and_qualified(
        self,
        session: AsyncSession,
        *,
        enrollment_id: int,
        total_volume: Decimal,
        qualified_at: datetime | None,
    ) -> None:
        try:
            stmt = (
                update(Enrollment)
                .where(Enrollment.id == enrollment_id)
                .values(total_volume=total_volume, qualified_at=qualified_at)
            )
            await session.execute(stmt)
        except Exception as e:
            raise DatabaseError(
                f"Failed to update enrollment {enrollment_id}: {e}"
            ) from e

    async def leaderboard(
        self,
        session: AsyncSession,
        *,
        campaign_id: int,
        limit: int = 100,
    ) -> list[Enrollment]:
        """
        Top-N enrollments by total_volume DESC, ties broken by earlier created_at.

        Reads `total_volume` and `qualified_at` directly from enrollments —
        these are written by enrollment creation and the checker job.
        Leaderboard values are stale by up to one checker tick (~60s).
        """
        try:
            stmt = (
                select(Enrollment)
                .where(Enrollment.campaign_id == campaign_id)
                .order_by(desc(Enrollment.total_volume), asc(Enrollment.created_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(
                f"Failed to fetch leaderboard for campaign {campaign_id}: {e}"
            ) from e
    
    async def get_for_wallet_in_campaigns(
        self,
        session: AsyncSession,
        *,
        wallet_chain_id: int,
        wallet_address: str,
        campaign_ids: Sequence[int],
    ) -> dict[int, Enrollment]:
        """
        Bulk lookup: return enrollment rows for this wallet across the given
        campaigns, keyed by campaign_id. Missing keys mean the wallet isn't
        enrolled in that campaign.
        """
        if not campaign_ids:
            return {}
        try:
            stmt = select(Enrollment).where(
                and_(
                    Enrollment.wallet_chain_id == wallet_chain_id,
                    Enrollment.wallet_address == wallet_address,
                    Enrollment.campaign_id.in_(campaign_ids),
                )
            )
            result = await session.execute(stmt)
            return {e.campaign_id: e for e in result.scalars().all()}
        except Exception as e:
            raise DatabaseError(
                f"Failed to fetch enrollments for wallet {wallet_address}: {e}"
            ) from e

    async def list_active_for_recompute(
        self,
        session: AsyncSession,
        *,
        after_id: int,
        grace_cutoff: datetime,
        limit: int = 500,
    ) -> Sequence[Enrollment]:
        """
        Cursor-paginated fetch of enrollments whose campaign window is open
        OR has ended within the grace period. Returns enrollments with id > after_id,
        ordered by id for stable cursor pagination.

        Used by the checker job to re-aggregate volume periodically.
        Includes already-qualified enrollments because the leaderboard shows
        live `total_volume` for everyone.
        """
        try:
            now = datetime.now(timezone.utc)
            stmt = (
                select(Enrollment)
                .join(Campaign, Enrollment.campaign_id == Campaign.id)
                .where(
                    and_(
                        Enrollment.id > after_id,
                        Campaign.starts_at <= now,
                        Campaign.ends_at >= grace_cutoff,
                    )
                )
                .order_by(Enrollment.id)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(
                f"Failed to fetch enrollments for recompute: {e}"
            ) from e