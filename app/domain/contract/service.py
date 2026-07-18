# app/domain/contract/service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contract.repo import ContractRepository
from app.domain.contract.schema import ProtocolOutSchema
from app.core.logger import get_logger

logger = get_logger(__name__)


class ContractService:
    def __init__(self, repo: ContractRepository):
        self.repo = repo

    async def list_protocols(self, session, chain_id):
        rows = await self.repo.list_distinct_protocols(session, chain_id)
        return [ProtocolOutSchema.model_validate(r) for r in rows]
