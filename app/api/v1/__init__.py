from fastapi import APIRouter

from app.core.config import settings

from .transfers import router as transfers_router
from .stats import router as stats_router
from .tokens import router as tokens_router
from .protocols import router as protocols_router
from .campaigns import router as campaigns_router
from .wallets import router as wallets_router
from .auth import router as auth_router

router = APIRouter(
    prefix=settings.api.v1.prefix,
)

router.include_router(transfers_router)
router.include_router(stats_router)
router.include_router(tokens_router)
router.include_router(protocols_router)
router.include_router(campaigns_router)
router.include_router(wallets_router)
router.include_router(auth_router)

__all__ = ["router"]
