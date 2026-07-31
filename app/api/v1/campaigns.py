# app/api/v1/campaigns.py
from fastapi import APIRouter, Depends, Query, Request, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_session
from app.api.dependencies.auth import get_current_wallet
from app.api.dependencies.services import (
    get_campaign_service,
    get_enrollment_service,
    get_finalizer_service
)
from app.domain.campaign.finalizer_service import (
    FinalizationError,
    CampaignNotFound,
    AlreadyFinalized,
    CampaignNotEnded
)
from app.domain.enrollment.schema import (
    EnrollmentOutSchema, LeaderboardEntrySchema
)
from app.core.config import settings
from app.domain.campaign.schema import (
    CampaignCreateSchema,
    CampaignOutSchema,
    ClaimProofSchema
)
from app.domain.campaign.finalizer_service import FinalizerService
from app.domain.campaign.service import CampaignService
from app.domain.enrollment.service import EnrollmentService
from app.middleware.rate_limiter import limiter
from app.domain.auth.schema import AuthenticatedWallet


router = APIRouter(prefix=settings.api.v1.campaign, tags=["Campaigns"])


@router.get("", response_model=list[CampaignOutSchema])
@limiter.limit("60/minute")
async def list_campaigns(
    request: Request,
    chain_id: int | None = Query(None, alias="chainId", description="EVM Chain ID filter"),
    session: AsyncSession = Depends(get_session),
    service: CampaignService = Depends(get_campaign_service),
):
    """List active campaigns (starts_at <= now <= ends_at)."""
    return await service.list_by_chain(session=session, chain_id=chain_id)


@router.post(
    "",
    response_model=CampaignOutSchema,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def create_campaign(
    request: Request,
    payload: CampaignCreateSchema,
    session: AsyncSession = Depends(get_session),
    service: CampaignService = Depends(get_campaign_service),
):
    """Create a new campaign. Auth will be added in week 4."""
    return await service.create_campaign(session=session, payload=payload)


@router.delete(
    "/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("10/minute")
async def delete_campaign(
    request: Request,
    campaign_id: int,
    session: AsyncSession = Depends(get_session),
    service: CampaignService = Depends(get_campaign_service),
):
    """Delete a campaign. Auth will be added in week 4."""
    await service.delete_campaign(session=session, campaign_id=campaign_id)


@router.post(
    "/{campaign_id}/enroll",
    response_model=EnrollmentOutSchema,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
async def enroll_in_campaign(
    request: Request,
    campaign_id: int,
    wallet: AuthenticatedWallet = Depends(get_current_wallet),
    session: AsyncSession = Depends(get_session),
    service: EnrollmentService = Depends(get_enrollment_service),
):
    """
    Enroll the authenticated wallet in a campaign.

    Atomic transaction: reserve a slot (409 if full), upsert the wallet, insert
    the enrollment row, compute historical transfer volume in the campaign window,
    set `qualified_at` if threshold met. All-or-nothing.

    Returns 201 on first enrollment, 409 if already enrolled or campaign is full,
    404 if the campaign doesn't exist, 400 if the campaign hasn't started or has
    ended.

    Phase 1: wallet is hardcoded via `get_current_wallet`. Phase 1.5: SIWE-derived
    from JWT.
    """
    return await service.enroll(
        session=session,
        campaign_id=campaign_id,
        wallet_chain_id=wallet.chain_id,
        wallet_address=wallet.address,
    )


@router.get(
    "/{campaign_id}/leaderboard",
    response_model=list[LeaderboardEntrySchema],
)
@limiter.limit("60/minute")
async def get_campaign_leaderboard(
    request: Request,
    campaign_id: int,
    limit: int = Query(100, ge=1, le=100, description="Max entries to return"),
    session: AsyncSession = Depends(get_session),
    service: EnrollmentService = Depends(get_enrollment_service),
):
    """
    Top wallets in a campaign by cumulative transfer volume.

    Volume reflects the last checker pass (~60s stale). Sorted by volume DESC,
    earlier enrollers winning ties. Top 100 only; pagination not supported.
    """
    return await service.get_leaderboard(
        session=session,
        campaign_id=campaign_id,
        limit=limit,
    )



@router.post("/{campaign_id}/finalize", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def finalize(
    request: Request,
    campaign_id: int,
    session: AsyncSession = Depends(get_session),
    service: FinalizerService = Depends(get_finalizer_service),
):
    """Operator-triggered finalization. Service enforces the rules
    (exists / ended / not-already-finalized); the route maps its typed errors
    to HTTP status codes."""
    try:
        root = await service.finalize_campaign(session, campaign_id)
    except CampaignNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (CampaignNotEnded, AlreadyFinalized) as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e)) from e
    except FinalizationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return {
        "campaignId": root.campaign_id,
        "status": root.status,
        "winnerCount": root.winner_count,
        "rootHash": "0x" + root.root_hash.hex(),
    }


@router.get("/{campaign_id}/proof/{address}", response_model=ClaimProofSchema)
@limiter.limit("60/minute")
async def get_claim_proof(
    request: Request,
    campaign_id: int,
    address: str,
    session: AsyncSession = Depends(get_session),
    service: FinalizerService = Depends(get_finalizer_service),
):
    """Return a wallet's reward amount + Merkle proof for a finalized campaign.
    The frontend passes `amount` and `proof` straight into the on-chain
    claim(campaignId, account, amount, proof) call."""
    claim = await service.get_claim_proof(session, campaign_id, address)
    if claim is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="no reward claim for this wallet in this campaign",
        )
    return ClaimProofSchema(
        campaign_id=claim.campaign_id,
        wallet_address=claim.wallet_address,
        amount=str(int(claim.amount)),
        leaf_index=claim.leaf_index,
        proof=claim.proof,
        claimed=claim.claimed_at is not None,
    )