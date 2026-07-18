# app/domain/processed_block/repo.py
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.base_repository import BaseRepository
from app.domain.processed_block.model import ProcessedBlock
from app.exceptions.exceptions import DatabaseError


class ProcessedBlockRepository(BaseRepository[ProcessedBlock]):
    def __init__(self) -> None:
        super().__init__(ProcessedBlock)

    async def get_recent(
        self,
        session: AsyncSession,
        token: str,
        chain_id: int,
        limit: int = 50,
    ) -> list[ProcessedBlock]:
        """Return the most recent N processed blocks, newest first. For reorg walkback."""
        try:
            result = await session.execute(
                select(ProcessedBlock)
                .where(
                    ProcessedBlock.token == token.lower(),
                    ProcessedBlock.chain_id == chain_id,
                )
                .order_by(ProcessedBlock.block_number.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Failed to read recent processed blocks: {e}") from e

    async def insert_ignore(
        self,
        session: AsyncSession,
        token: str,
        chain_id: int,
        block_number: int,
        block_hash: str,
        parent_hash: str,
    ) -> None:
        """
        Record a processed block. Idempotent — silently skips if the row already exists.
        Reorg detection happens elsewhere; this is just the audit trail.
        """
        try:
            stmt = (
                pg_insert(ProcessedBlock)
                .values(
                    chain_id=chain_id,
                    token=token.lower(),
                    block_number=block_number,
                    block_hash=block_hash,
                    parent_hash=parent_hash,
                )
                .on_conflict_do_nothing(
                    index_elements=["chain_id", "token", "block_number"],
                )
            )
            await session.execute(stmt)
        except Exception as e:
            raise DatabaseError(f"Failed to insert processed block: {e}") from e