# tests/integration/test_finalizer.py
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.utils import merkle
from app.domain.campaign.finalizer_repo import FinalizerRepository
from app.domain.campaign.finalizer_service import (
    FinalizerService,
    FinalizationError,
)
from app.domain.campaign.model import Campaign, MerkleRoot, RewardClaim
from app.domain.enrollment.model import Enrollment
from app.domain.token.model import Token
from app.domain.wallet.model import Wallet
from app.enums.enums import MerkleRootStatus

PAST = datetime.now(timezone.utc) - timedelta(days=1)
FUTURE = datetime.now(timezone.utc) + timedelta(days=1)

CHAIN = 1
TOKEN_ADDR = "0x" + "a" * 40

A1 = "0x1111111111111111111111111111111111111111"
A2 = "0x2222222222222222222222222222222222222222"
A3 = "0x3333333333333333333333333333333333333333"


@pytest.fixture
def service() -> FinalizerService:
    return FinalizerService(FinalizerRepository())


async def _seed_token(db_session):
    db_session.add(Token(
        chain_id=CHAIN,
        address=TOKEN_ADDR,
        name="Test Token",
        symbol="TKN",
        decimals=18,
    ))
    await db_session.flush()


async def _mk_campaign(db_session, *, reward_amount: int, ends_at=PAST) -> Campaign:
    c = Campaign(
        name="t",
        chain_id=CHAIN,
        token_address=TOKEN_ADDR,
        min_total_volume=Decimal(0),
        duration_days=7,
        reward_amount=Decimal(reward_amount),
        starts_at=PAST - timedelta(days=7),
        ends_at=ends_at,
        max_recipients=100,
        enrolled_count=0,
    )
    db_session.add(c)
    await db_session.flush()
    return c


async def _qualify(db_session, campaign_id: int, address: str, volume: int):
    db_session.add(Wallet(chain_id=CHAIN, address=address.lower()))
    await db_session.flush()
    db_session.add(
        Enrollment(
            campaign_id=campaign_id,
            wallet_chain_id=CHAIN,
            wallet_address=address.lower(),
            total_volume=Decimal(volume),
            qualified_at=PAST,
        )
    )
    await db_session.flush()


def _verify(leaf: bytes, proof_hex: list[str], root: bytes) -> bool:
    h = leaf
    for s in proof_hex:
        h = merkle._hash_pair(h, bytes.fromhex(s[2:]))
    return h == root


@pytest.mark.asyncio
async def test_normal_split_three_winners(db_session, service):
    await _seed_token(db_session)
    c = await _mk_campaign(db_session, reward_amount=1000)
    for a in (A1, A2, A3):
        await _qualify(db_session, c.id, a, 100)

    root = await service.finalize_campaign(db_session, c.id)
    await db_session.flush()

    assert root.status == MerkleRootStatus.pending.value
    assert root.winner_count == 3
    assert int(root.total_amount) == 1000

    claims = (await db_session.execute(
        RewardClaim.__table__.select().where(RewardClaim.campaign_id == c.id)
    )).all()
    assert len(claims) == 3
    amounts = sorted(int(r.amount) for r in claims)
    assert amounts == [333, 333, 334]
    assert sum(amounts) == 1000


@pytest.mark.asyncio
async def test_zero_winners(db_session, service):
    await _seed_token(db_session)
    c = await _mk_campaign(db_session, reward_amount=1000)

    root = await service.finalize_campaign(db_session, c.id)
    await db_session.flush()

    assert root.status == MerkleRootStatus.no_winners.value
    assert root.winner_count == 0
    claims = (await db_session.execute(
        RewardClaim.__table__.select().where(RewardClaim.campaign_id == c.id)
    )).all()
    assert len(claims) == 0


@pytest.mark.asyncio
async def test_one_winner_padded(db_session, service):
    await _seed_token(db_session)
    c = await _mk_campaign(db_session, reward_amount=1000)
    await _qualify(db_session, c.id, A1, 100)

    root = await service.finalize_campaign(db_session, c.id)
    await db_session.flush()

    assert root.winner_count == 1
    claims = (await db_session.execute(
        RewardClaim.__table__.select().where(RewardClaim.campaign_id == c.id)
    )).all()
    assert len(claims) == 1
    claim = claims[0]
    assert int(claim.amount) == 1000

    leaf = merkle.leaf_hash(A1.lower(), 1000)
    assert _verify(leaf, claim.proof, root.root_hash)


@pytest.mark.asyncio
async def test_not_ended_raises(db_session, service):
    await _seed_token(db_session)
    c = await _mk_campaign(db_session, reward_amount=1000, ends_at=FUTURE)
    with pytest.raises(FinalizationError):
        await service.finalize_campaign(db_session, c.id)


@pytest.mark.asyncio
async def test_double_finalize_raises(db_session, service):
    await _seed_token(db_session)
    c = await _mk_campaign(db_session, reward_amount=1000)
    await _qualify(db_session, c.id, A1, 100)
    await _qualify(db_session, c.id, A2, 100)

    await service.finalize_campaign(db_session, c.id)
    await db_session.flush()
    with pytest.raises(FinalizationError):
        await service.finalize_campaign(db_session, c.id)