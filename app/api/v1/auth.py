# app/api/v1/auth.py
from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_wallet
from app.api.dependencies.db import get_session
from app.api.dependencies.integrations import get_redis
from app.api.dependencies.services import get_auth_service
from app.core.config import settings
from app.domain.auth.schema import (
    AuthenticatedWallet,
    NonceRequest,
    NonceResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.domain.auth.service import AuthService
from app.middleware.rate_limiter import limiter


router = APIRouter(prefix=settings.api.v1.auth, tags=["Auth"])


@router.post("/nonce", response_model=NonceResponse)
@limiter.limit("10/minute")
async def request_nonce(
    request: Request,
    body: NonceRequest,
    redis: Redis = Depends(get_redis),
    service: AuthService = Depends(get_auth_service),
):
    return await service.request_nonce(redis, address=body.address)


@router.post("/verify", response_model=VerifyResponse)
@limiter.limit("10/minute")
async def verify(
    request: Request,
    response: Response,
    body: VerifyRequest,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    service: AuthService = Depends(get_auth_service),
):
    verify_response, token = await service.verify(
        session=session,
        redis=redis,
        message=body.message,
        signature=body.signature,
    )

    response.set_cookie(
        key=settings.siwe.jwt_cookie_name,
        value=token,
        max_age=settings.siwe.jwt_expire_hours * 3600,
        httponly=True,
        secure=settings.siwe.cookie_secure,
        samesite="lax",
    )
    return verify_response


@router.post("/logout", status_code=204)
@limiter.limit("60/minute")
async def logout(
    request: Request,
    response: Response,
):
    response.delete_cookie(
        key=settings.siwe.jwt_cookie_name,
        httponly=True,
        secure=settings.siwe.cookie_secure,
        samesite="lax",
    )


@router.get("/me", response_model=AuthenticatedWallet)
@limiter.limit("60/minute")
async def me(
    request: Request,
    wallet: AuthenticatedWallet = Depends(get_current_wallet),
):
    return wallet