# scripts/wipe_dev_database.py
"""
Wipe all dev data from the database, preserving migration state.

Truncates every domain table with RESTART IDENTITY CASCADE — rows gone,
sequences reset to 1, FK dependencies handled automatically.

Preserves:
  - alembic_version (migration state)

Run:
    python -m scripts.wipe_dev_database
    python -m scripts.wipe_dev_database --yes   # skip confirmation prompt

WARNING: this is destructive. Do not run against a production database.
"""
from __future__ import annotations

import asyncio
import argparse
import sys

from sqlalchemy import text

from app.core.config import settings
from app.core.logger import get_logger, setup_logging
from app.database.connection import db_manager

logger = get_logger(__name__)

# Tables to wipe — everything except alembic_version
DOMAIN_TABLES = [
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


def _refuse_if_production() -> None:
    """
    Defensive guard. Refuses to run if the configured environment looks
    like production. Adjust the check to match your settings shape.
    """
    env = getattr(settings, "environment", None) or getattr(settings, "env", None)
    if env and "prod" in str(env).lower():
        logger.error("refusing to wipe — environment looks like production (%s)", env)
        sys.exit(1)


def _confirm(skip: bool) -> None:
    if skip:
        return
    print("This will DELETE all data from the following tables:")
    for t in DOMAIN_TABLES:
        print(f"  - {t}")
    print("alembic_version will be preserved.")
    answer = input("Type 'wipe' to confirm: ")
    if answer.strip() != "wipe":
        print("aborted.")
        sys.exit(0)


async def wipe() -> None:
    db_manager.init_engine()
    async with db_manager.session_scope() as session:
        # Single TRUNCATE statement — CASCADE handles FK deps, RESTART IDENTITY resets sequences
        table_list = ", ".join(DOMAIN_TABLES)
        await session.execute(
            text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE")
        )
        await session.commit()
    await db_manager.close()
    logger.info("wiped %d tables (sequences reset, alembic_version preserved)", len(DOMAIN_TABLES))


async def main(skip_confirm: bool) -> None:
    _refuse_if_production()
    _confirm(skip_confirm)
    await wipe()


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--yes", dest="skip_confirm", action="store_true",
        help="skip the confirmation prompt",
    )
    args = parser.parse_args()
    asyncio.run(main(skip_confirm=args.skip_confirm))
