# app/api/v1/tokens.py
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.token.schema import TokenOutSchema
from app.domain.token.service import TokenService
from app.api.dependencies.db import get_session
from app.api.dependencies.services import get_token_service
from app.core.config import settings
from app.middleware.rate_limiter import limiter


router = APIRouter(prefix=settings.api.v1.token, tags=["Tokens"])


@router.get("", response_model=list[TokenOutSchema])
@limiter.limit("60/minute")
async def list_tokens(
    request: Request,
    chain_id: int | None = Query(None, alias="chainId", description="EVM Chain ID filter"),
    session: AsyncSession = Depends(get_session),
    service: TokenService = Depends(get_token_service),
):
    return await service.list_active(session=session, chain_id=chain_id)
