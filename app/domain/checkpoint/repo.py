# app/domain/checkpoint/repo.py
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.base_repository import BaseRepository
from app.domain.checkpoint.model import Checkpoint
from app.exceptions.exceptions import DatabaseError


class CheckpointRepository(BaseRepository[Checkpoint]):
    def __init__(self) -> None:
        super().__init__(Checkpoint)

    async def get_last_block(
        self,
        session: AsyncSession,
        token: str,
        chain_id: int,
    ) -> int | None:
        try:
            result = await session.execute(
                select(Checkpoint.last_block).where(
                    Checkpoint.token == token.lower(),
                    Checkpoint.chain_id == chain_id,
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(f"Failed to read checkpoint: {e}") from e

    async def upsert(
        self,
        session: AsyncSession,
        token: str,
        chain_id: int,
        last_block: int,
    ) -> None:
        try:
            stmt = (
                pg_insert(Checkpoint)
                .values(token=token.lower(), chain_id=chain_id, last_block=last_block)
                .on_conflict_do_update(
                    index_elements=["chain_id", "token"],
                    set_={
                        "last_block": last_block,
                        "updated_at": func.now(),  # type: ignore[no-untyped-call]
                    },
                )
            )
            await session.execute(stmt)
        except Exception as e:
            raise DatabaseError(f"Failed to upsert checkpoint: {e}") from e