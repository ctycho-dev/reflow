# app/api/v1/wallets.py — new file

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_session
from app.api.dependencies.services import get_enrollment_service
from app.api.dependencies.services import get_reward_service
from app.core.config import settings
from app.domain.enrollment.schema import WalletEligibilitySchema
from app.domain.enrollment.service import EnrollmentService
from app.domain.campaign.schema import WalletClaimSchema
from app.domain.campaign.reward_service import RewardService
from app.middleware.rate_limiter import limiter


router = APIRouter(prefix=settings.api.v1.wallet, tags=["Wallets"])


@router.get(
    "/{address}/eligibility",
    response_model=WalletEligibilitySchema,
)
@limiter.limit("60/minute")
async def get_wallet_eligibility(
    request: Request,
    address: str,
    chain_id: int = Query(1, description="EVM Chain ID"),
    session: AsyncSession = Depends(get_session),
    service: EnrollmentService = Depends(get_enrollment_service),
):
    """
    Cross-campaign eligibility snapshot for a wallet.

    Returns the wallet's status (enrolled, qualified, current volume, progress)
    for every currently-active campaign plus recently-ended ones within the
    grace period.
    """
    return await service.get_wallet_eligibility(
        session=session,
        chain_id=chain_id,
        wallet_address=address,
    )


@router.get("/{address}/claims", response_model=list[WalletClaimSchema])
@limiter.limit("60/minute")
async def get_wallet_claims(
    request: Request,
    address: str,
    session: AsyncSession = Depends(get_session),
    service: RewardService = Depends(get_reward_service),
):
    """
    All reward claims for a wallet across campaigns.

    `claimed` is live truth mirrored from on-chain Claimed events; `rootStatus`
    is the settlement state — only 'confirmed' claims are claimable on-chain.
    """
    return await service.list_wallet_claims(session=session, wallet_address=address)
