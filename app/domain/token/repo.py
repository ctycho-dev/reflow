# app/domain/token/repo.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.base_repository import BaseRepository
from app.domain.token.model import Token


class TokenRepository(BaseRepository[Token]):
    def __init__(self) -> None:
        super().__init__(Token)

    async def get_active_tokens(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> list[Token]:
        result = await session.execute(
            select(Token).where(
                Token.chain_id == chain_id,
                Token.is_active.is_(True),
            )
        )
        return list(result.scalars().all())
    
    async def get_tokens_map(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> dict[str, dict]:
        result = await session.execute(
            select(Token).where(Token.chain_id == chain_id)
        )
        tokens = result.scalars().all()
        return {
            token.address.lower(): {
                "address": token.address.lower(),
                "symbol": token.symbol,
                "name": token.name,
                "decimals": token.decimals,
                "color": token.color,
            }
            for token in tokens
        }
    
    async def list_active(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> list[Token]:
        result = await session.execute(
            select(Token)
            .where(Token.chain_id == chain_id, Token.is_active.is_(True))
            .order_by(Token.symbol)
        )
        return list(result.scalars().all())

    async def exists(
        self,
        session: AsyncSession,
        *,
        chain_id: int,
        address: str,
    ) -> bool:
        """Cheap existence check — returns True if the token is indexed."""
        stmt = (
            select(Token.address)
            .where(
                Token.chain_id == chain_id,
                Token.address == address.lower(),
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None