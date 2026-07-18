# app/domain/wallet/repo.py
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.base_repository import BaseRepository
from app.domain.wallet.model import Wallet
from app.exceptions.exceptions import DatabaseError


class WalletRepository(BaseRepository[Wallet]):
    def __init__(self) -> None:
        super().__init__(Wallet)

    async def get_watched_addresses(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> set[str]:
        """Return lowercase addresses for O(1) membership checks in the event loop."""
        result = await session.execute(
            select(Wallet.address).where(Wallet.chain_id == chain_id)
        )
        return {row for row in result.scalars().all()}
    
    async def upsert(
        self,
        session: AsyncSession,
        *,
        chain_id: int,
        address: str,
    ) -> None:
        """
        Idempotent wallet insert. No-op if (chain_id, address) already exists.
        """
        try:
            stmt = (
                pg_insert(Wallet)
                .values(chain_id=chain_id, address=address)
                .on_conflict_do_nothing(index_elements=["chain_id", "address"])
            )
            await session.execute(stmt)
        except Exception as e:
            raise DatabaseError(f"Failed to upsert wallet {address}: {e}") from e
