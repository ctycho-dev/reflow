from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.stats.schema import ProtocolStatSchema
from app.domain.stats.service import StatsService
from app.api.dependencies.db import get_session
from app.api.dependencies.services import get_stats_service
from app.core.config import settings
from app.middleware.rate_limiter import limiter

router = APIRouter(prefix=settings.api.v1.stats, tags=["Stats"])


@router.get("", response_model=list[ProtocolStatSchema])
@limiter.limit("60/minute")
async def get_stats(
    request: Request,
    chain_id: int = Query(1, description="EVM Chain ID"),
    session: AsyncSession = Depends(get_session),
    service: StatsService = Depends(get_stats_service),
):
    return await service.get_protocol_stats(session=session, chain_id=chain_id)