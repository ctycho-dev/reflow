# app/domain/campaign/finalizer_service.py
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.campaign.finalizer_repo import FinalizerRepository
from app.domain.campaign.distribution import equal_split
from app.domain.campaign.model import MerkleRoot, RewardClaim
from app.utils import merkle

ZERO_ADDRESS = "0x" + "0" * 40


class FinalizationError(Exception): pass
class CampaignNotFound(FinalizationError): pass
class CampaignNotEnded(FinalizationError): pass
class AlreadyFinalized(FinalizationError): pass


def _encode_proof(proof: list[bytes]) -> list[str]:
    """bytes siblings -> 0x-prefixed hex strings for JSONB storage."""
    return ["0x" + sibling.hex() for sibling in proof]


class FinalizerService:
    """Campaign finalization: compute winners + equal-split reward, build the
    Merkle tree, persist root + claims (status=pending). Does NOT touch chain —
    broadcasting setMerkleRoot is the signer worker's job (Stage 4)."""

    def __init__(self, repo: FinalizerRepository):
        self.repo = repo

    async def finalize_campaign(
        self, session: AsyncSession, campaign_id: int
    ) -> MerkleRoot:
        campaign = await self.repo.get_campaign(session, campaign_id)
        if campaign is None:
            raise CampaignNotFound(f"campaign {campaign_id} not found")

        if campaign.ends_at > datetime.now(timezone.utc):
            raise CampaignNotEnded(f"campaign {campaign_id} has not ended yet")

        existing = await self.repo.get_existing_root(session, campaign_id)
        if existing is not None:
            raise AlreadyFinalized(f"campaign {campaign_id} already finalized")

        winners = await self.repo.get_qualified_winners(session, campaign_id)

        # zero winners: terminal state, no claims, no on-chain root
        if len(winners) == 0:
            return await self.repo.persist_no_winners(
                session, campaign_id=campaign_id, chain_id=campaign.chain_id
            )

        # equal-split amounts (dust -> first winner)
        pool = int(campaign.reward_amount)
        addresses = [addr for addr, _vol in winners]
        amounts = equal_split(pool, len(addresses))
        tree_winners: list[tuple[str, int]] = list(zip(addresses, amounts))

        # one winner: pad to a 2-leaf tree with an unclaimable (zero, 0) dummy.
        # The dummy is in the tree but nobody controls it; only the real winner
        # gets a reward_claims row.
        padded = False
        if len(tree_winners) == 1:
            tree_winners = tree_winners + [(ZERO_ADDRESS, 0)]
            padded = True

        root_hash, proofs = merkle.build_tree(tree_winners)

        real_count = 1 if padded else len(tree_winners)
        claims: list[dict] = []
        for leaf_index, (addr, amount) in enumerate(tree_winners[:real_count]):
            claims.append(
                {
                    "wallet_address": addr.lower(),
                    "amount": Decimal(amount),
                    "leaf_index": leaf_index,
                    "proof": _encode_proof(proofs[addr.lower()]),
                }
            )

        return await self.repo.persist_finalization(
            session,
            campaign_id=campaign_id,
            chain_id=campaign.chain_id,
            root_hash=root_hash,
            total_amount=Decimal(pool),
            winner_count=real_count,
            claims=claims,
        )

    async def get_claim_proof(
        self, session: AsyncSession, campaign_id: int, wallet_address: str
    ) -> RewardClaim | None:
        """Fetch a wallet's stored claim (amount + proof) for a finalized
        campaign. Returns None if the wallet has no claim row."""
        return await self.repo.get_claim(session, campaign_id, wallet_address)