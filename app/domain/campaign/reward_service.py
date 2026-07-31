# app/domain/campaign/reward_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.campaign.reward_repo import RewardClaimRepository
from app.domain.campaign.schema import WalletClaimSchema


class RewardService:
    def __init__(self, repo: RewardClaimRepository):
        self.repo = repo

    async def list_wallet_claims(
        self, session: AsyncSession, wallet_address: str
    ) -> list[WalletClaimSchema]:
        rows = await self.repo.list_for_wallet(session, wallet_address=wallet_address)
        return [
            WalletClaimSchema(
                campaign_id=r["campaign_id"],
                campaign_name=r["campaign_name"],
                chain_id=r["chain_id"],
                amount=str(int(r["amount"])),
                claimed=r["claimed_at"] is not None,
                claim_tx_hash="0x" + r["claim_tx_hash"].hex() if r["claim_tx_hash"] else None,
                root_status=r["root_status"],
            )
            for r in rows
        ]
