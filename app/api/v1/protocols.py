# app/api/v1/protocols.py
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contract.schema import ProtocolOutSchema
from app.domain.contract.service import ContractService
from app.api.dependencies.db import get_session
from app.api.dependencies.services import get_contract_service
from app.core.config import settings
from app.middleware.rate_limiter import limiter


router = APIRouter(prefix=settings.api.v1.contract, tags=["Protocols"])


@router.get("", response_model=list[ProtocolOutSchema])
@limiter.limit("60/minute")
async def list_protocols(
    request: Request,
    chain_id: int | None = Query(None, alias="chainId", description="EVM Chain ID filter"),
    session: AsyncSession = Depends(get_session),
    service: ContractService = Depends(get_contract_service),
):
    return await service.list_protocols(session=session, chain_id=chain_id)
