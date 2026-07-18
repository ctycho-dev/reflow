# app/domain/token/service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.token.repo import TokenRepository
from app.domain.token.schema import TokenOutSchema
from app.core.logger import get_logger

logger = get_logger(__name__)


class TokenService:
    def __init__(self, repo: TokenRepository):
        self.repo = repo

    async def list_active(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> list[TokenOutSchema]:
        tokens = await self.repo.list_active(session, chain_id=chain_id)

        return [
            TokenOutSchema.model_validate({
                "address": t.address.lower(),
                "symbol": t.symbol,
                "name": t.name,
                "decimals": t.decimals,
                "color": t.color,
            })
            for t in tokens
        ]