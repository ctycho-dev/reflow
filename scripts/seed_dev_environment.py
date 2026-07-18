# scripts/seed_dev_environment.py
"""
Wipe + seed a dev DB with realistic test data.

Reference data (tokens, protocol contracts) comes from seed_data.py — the
single source of truth. This script only owns dev-specific data:
campaigns, wallets, transfers, enrollments.

Run:
    python -m scripts.seed_dev_environment
    python -m scripts.seed_dev_environment --no-wipe
"""
from __future__ import annotations

import asyncio
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger, setup_logging
from app.database.connection import DatabaseManager
from app.domain.campaign.model import Campaign
from app.domain.contract.model import ProtocolContract
from app.domain.enrollment.model import Enrollment
from app.domain.token.model import Token
from app.domain.transfer.model import Transfer
from app.domain.wallet.model import Wallet
from app.core.sections import PostgresConfig

# Single source of truth for reference data
from scripts.seed_data import (
    CHAIN_ID_MAINNET,
    TOKENS,
    CONTRACTS,
    USDC,
    WEETH,
    AAVE_V2_AUSDC,
    AAVE_V3_AWETH,
    COMPOUND_V3_CUSDC,
    UNI_V3_USDC_WETH_005,
)

logger = get_logger(__name__)

CHAIN_ID = CHAIN_ID_MAINNET


# -----------------------------------------------------------------
# Dev-only data (test wallets, fake transfers, demo campaigns)
# -----------------------------------------------------------------

# 0x...01 is the hardcoded dev wallet (matches get_current_wallet)
WALLETS = [
    "0x0000000000000000000000000000000000000001",
    "0x1111111111111111111111111111111111111111",
    "0x2222222222222222222222222222222222222222",
    "0x3333333333333333333333333333333333333333",
    "0x4444444444444444444444444444444444444444",
    "0x5555555555555555555555555555555555555555",
]


# -----------------------------------------------------------------
# Reference-data seeders (idempotent, source from seed_data.py)
# -----------------------------------------------------------------

async def upsert_tokens(session: AsyncSession) -> None:
    stmt = pg_insert(Token).values(TOKENS).on_conflict_do_nothing(
        index_elements=["chain_id", "address"]
    )
    await session.execute(stmt)
    logger.info("seeded %d tokens", len(TOKENS))


async def upsert_contracts(session: AsyncSession) -> None:
    stmt = pg_insert(ProtocolContract).values(CONTRACTS).on_conflict_do_nothing(
        index_elements=["chain_id", "address"]
    )
    await session.execute(stmt)
    logger.info("seeded %d protocol contracts", len(CONTRACTS))


async def upsert_wallets(session: AsyncSession) -> None:
    rows = [{"chain_id": CHAIN_ID, "address": w} for w in WALLETS]
    stmt = pg_insert(Wallet).values(rows).on_conflict_do_nothing(
        index_elements=["chain_id", "address"]
    )
    await session.execute(stmt)
    logger.info("seeded %d wallets", len(WALLETS))


# -----------------------------------------------------------------
# Dev-data seeders
# -----------------------------------------------------------------

def _build_transfers() -> list[dict]:
    """
    Construct ~20 transfers across two tokens, several wallets, and the last
    14 days. Volume distribution is intentionally skewed so leaderboards have
    visible ranking.
    """
    now = datetime.now(timezone.utc)
    transfers: list[dict] = []
    block_number = 19_500_000
    log_index = 0

    def add(wallet: str, counterparty: str, token: str, amount: Decimal, days_ago: float) -> None:
        nonlocal block_number, log_index
        block_number += 1
        log_index = (log_index + 1) % 50
        transfers.append({
            "chain_id": CHAIN_ID,
            "tx_hash": f"0x{block_number:064x}",
            "log_index": log_index,
            "block_number": block_number,
            "block_timestamp": now - timedelta(days=days_ago),
            "token": token,
            "from_address": wallet,
            "to_address": counterparty,
            "amount": amount,
        })

    USDC_UNIT = Decimal(10) ** 6
    WEETH_UNIT = Decimal(10) ** 18

    # Wallet 2: heavy USDC volume to Aave V2
    for i, days_ago in enumerate([13, 11, 9, 7, 5, 3, 1]):
        add(WALLETS[2], AAVE_V2_AUSDC, USDC, Decimal(5000 + i * 1000) * USDC_UNIT, days_ago)

    # Wallet 3: heavy weETH volume to Aave V3 aWETH
    for i, days_ago in enumerate([12, 10, 8, 6, 4, 2]):
        add(WALLETS[3], AAVE_V3_AWETH, WEETH, Decimal(3 + i) * WEETH_UNIT, days_ago)

    # Wallet 4: moderate USDC + Compound
    add(WALLETS[4], COMPOUND_V3_CUSDC, USDC, Decimal(2500) * USDC_UNIT, 8)
    add(WALLETS[4], COMPOUND_V3_CUSDC, USDC, Decimal(3500) * USDC_UNIT, 4)
    add(WALLETS[4], AAVE_V2_AUSDC, USDC, Decimal(1200) * USDC_UNIT, 2)

    # Wallet 5: moderate weETH
    add(WALLETS[5], AAVE_V3_AWETH, WEETH, Decimal(2) * WEETH_UNIT, 9)
    add(WALLETS[5], UNI_V3_USDC_WETH_005, WEETH, Decimal(1) * WEETH_UNIT, 5)

    # Wallet 1: tiny USDC activity
    add(WALLETS[1], AAVE_V2_AUSDC, USDC, Decimal(150) * USDC_UNIT, 6)

    # Wallet 0 (dev/hardcoded): one small transfer
    add(WALLETS[0], AAVE_V2_AUSDC, USDC, Decimal(50) * USDC_UNIT, 3)

    return transfers


async def seed_transfers(session: AsyncSession) -> None:
    rows = _build_transfers()
    stmt = pg_insert(Transfer).values(rows).on_conflict_do_nothing(
        index_elements=["chain_id", "tx_hash", "log_index"]
    )
    await session.execute(stmt)
    logger.info("seeded %d transfers", len(rows))


async def seed_campaigns(session: AsyncSession) -> list[Campaign]:
    now = datetime.now(timezone.utc)

    rows = [
        # Active USDC campaign — ongoing
        {
            "name": "USDC Power Users",
            "description": "Top USDC suppliers to Aave V2 — active",
            "chain_id": CHAIN_ID,
            "token_address": USDC,
            "target_contract_address": AAVE_V2_AUSDC,
            "min_total_volume": Decimal(1000) * (Decimal(10) ** 6),
            "reward_amount": Decimal(100),
            "duration_days": 14,
            "starts_at": now - timedelta(days=10),
            "ends_at": now + timedelta(days=4),
            "max_recipients": 100,
            "enrolled_count": 0,
        },
        # Active weETH campaign — ongoing
        {
            "name": "weETH Holders",
            "description": "Suppliers to Aave V3 aWETH market — active",
            "chain_id": CHAIN_ID,
            "token_address": WEETH,
            "target_contract_address": AAVE_V3_AWETH,
            "min_total_volume": Decimal(1) * (Decimal(10) ** 18),
            "reward_amount": Decimal(250),
            "duration_days": 14,
            "starts_at": now - timedelta(days=10),
            "ends_at": now + timedelta(days=4),
            "max_recipients": 50,
            "enrolled_count": 0,
        },
        # Future campaign — hasn't started
        {
            "name": "Upcoming USDC Sprint",
            "description": "Pre-launch sprint — starts soon",
            "chain_id": CHAIN_ID,
            "token_address": USDC,
            "target_contract_address": COMPOUND_V3_CUSDC,
            "min_total_volume": Decimal(500) * (Decimal(10) ** 6),
            "reward_amount": Decimal(75),
            "duration_days": 7,
            "starts_at": now + timedelta(days=2),
            "ends_at": now + timedelta(days=9),
            "max_recipients": 200,
            "enrolled_count": 0,
        },
        # Ended campaign — past
        {
            "name": "Early USDC Adopters",
            "description": "Past campaign — for ended-list view",
            "chain_id": CHAIN_ID,
            "token_address": USDC,
            "target_contract_address": AAVE_V2_AUSDC,
            "min_total_volume": Decimal(500) * (Decimal(10) ** 6),
            "reward_amount": Decimal(50),
            "duration_days": 7,
            "starts_at": now - timedelta(days=20),
            "ends_at": now - timedelta(days=13),
            "max_recipients": 100,
            "enrolled_count": 0,
        },
    ]

    created: list[Campaign] = []
    for row in rows:
        campaign = Campaign(**row)
        session.add(campaign)
        created.append(campaign)
    await session.flush()
    logger.info("seeded %d campaigns: %s", len(created), [c.name for c in created])
    return created


async def seed_enrollments(session: AsyncSession, campaigns: list[Campaign]) -> None:
    """
    Enroll several wallets in the two active campaigns with mock volumes.
    The checker job will recompute these from actual transfers on its first tick.
    """
    active_usdc = next(c for c in campaigns if c.name == "USDC Power Users")
    active_weeth = next(c for c in campaigns if c.name == "weETH Holders")

    USDC_UNIT = Decimal(10) ** 6
    WEETH_UNIT = Decimal(10) ** 18
    now = datetime.now(timezone.utc)

    rows = [
        {"campaign": active_usdc, "wallet": WALLETS[2], "volume": Decimal(35000) * USDC_UNIT, "qualified": True},
        {"campaign": active_usdc, "wallet": WALLETS[4], "volume": Decimal(7200) * USDC_UNIT, "qualified": True},
        {"campaign": active_usdc, "wallet": WALLETS[1], "volume": Decimal(150) * USDC_UNIT, "qualified": False},
        {"campaign": active_usdc, "wallet": WALLETS[0], "volume": Decimal(50) * USDC_UNIT, "qualified": False},

        {"campaign": active_weeth, "wallet": WALLETS[3], "volume": Decimal(33) * WEETH_UNIT, "qualified": True},
        {"campaign": active_weeth, "wallet": WALLETS[5], "volume": Decimal(3) * WEETH_UNIT, "qualified": True},
    ]

    for row in rows:
        e = Enrollment(
            wallet_chain_id=CHAIN_ID,
            wallet_address=row["wallet"],
            campaign_id=row["campaign"].id,
            total_volume=row["volume"],
            qualified_at=now if row["qualified"] else None,
        )
        session.add(e)
        row["campaign"].enrolled_count += 1

    await session.flush()
    logger.info("seeded %d enrollments across %d campaigns", len(rows), 2)


# -----------------------------------------------------------------
# Wipe
# -----------------------------------------------------------------

WIPE_ORDER = [
    "enrollments",
    "rewards",
    "campaigns",
    "transfers",
    "wallets",
    "processed_blocks",
    "checkpoints",
    "protocol_contracts",
    "tokens",
]


async def wipe(session: AsyncSession) -> None:
    for table in WIPE_ORDER:
        await session.execute(text(f"DELETE FROM {table}"))
    logger.warning("wiped tables: %s", WIPE_ORDER)


# -----------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------

async def main(do_wipe: bool) -> None:
    db_manager = DatabaseManager(PostgresConfig())
    db_manager.init_engine(application_name="reflow-signer")

    async with db_manager.session_scope() as session:
        if do_wipe:
            await wipe(session)

        await upsert_tokens(session)
        await upsert_contracts(session)
        await upsert_wallets(session)
        await seed_transfers(session)
        campaigns = await seed_campaigns(session)
        await seed_enrollments(session, campaigns)

        await session.commit()

    await db_manager.close()
    logger.info("seed complete.")


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-wipe", dest="wipe", action="store_false",
        help="Don't wipe existing data, just append (idempotent inserts only)",
    )
    parser.set_defaults(wipe=True)
    args = parser.parse_args()
    asyncio.run(main(do_wipe=args.wipe))
