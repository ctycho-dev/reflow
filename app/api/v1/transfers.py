import asyncio
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.redis.pubsub import RedisPubSub
from app.domain.transfer.schema import TransferOutSchema
from app.domain.transfer.service import TransferService
from app.api.dependencies.db import get_session
from app.api.dependencies.services import get_transfer_service
from app.core.config import settings
from app.middleware.rate_limiter import limiter


router = APIRouter(prefix=settings.api.v1.transfer, tags=["Transfers"])


@router.get("", response_model=list[TransferOutSchema])
@limiter.limit("60/minute")
async def list_transfers(
    request: Request,
    chain_id: int = Query(1, description="EVM Chain ID"),
    token: str | None = Query(None, description="Token contract address"),
    protocol: str | None = Query(None, description="Protocol name, e.g. 'Aave V3'"),
    limit: int = Query(100, le=200),
    session: AsyncSession = Depends(get_session),
    service: TransferService = Depends(get_transfer_service),
):
    return await service.get_recent(
        session=session,
        chain_id=chain_id,
        token=token,
        protocol=protocol,
        limit=limit,
    )


async def _event_generator(request: Request, chain_id: int):
    pubsub = RedisPubSub(
        client=request.app.state.redis.client,
        channel="transfers",
        object_id=str(chain_id),
        client_id="sse",
    )
    await pubsub.subscribe()
    try:
        async for message in pubsub.listen():
            if await request.is_disconnected():
                break
            yield f"data: {message}\n\n"
            # Heartbeat every 30s to keep connection alive through proxies
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe()


@router.get("/stream")
@limiter.limit("50/minute")
async def stream_transfers(
    request: Request,
    chain_id: int = Query(1, description="EVM Chain ID"),
):
    return StreamingResponse(
        _event_generator(request, chain_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disables Nginx buffering
        },
    )