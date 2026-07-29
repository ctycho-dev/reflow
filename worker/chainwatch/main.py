# jobs/chainwatch/main.py
import asyncio
import signal

from web3 import AsyncWeb3
from web3.providers import WebSocketProvider

from app.core.sections import PostgresConfig, BlockchainConfig
from app.database.connection import DatabaseManager
from worker.chainwatch.watcher import watch_token
from worker.chainwatch.claim_watcher import ClaimWatcher
from worker.chainwatch.persistence import ChainwatchPersistence
from app.core.logger import get_logger, setup_logging

# ==============================
# python3 -m worker.chainwatch.main
# ==============================

logger = get_logger(__name__)


async def main() -> None:
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    blockchain = BlockchainConfig()
    db = DatabaseManager(PostgresConfig())
    db.init_engine(application_name="reflow-chainwatch")

    logger.debug("Connecting to %s...", blockchain.ws_url[:40])

    async with AsyncWeb3(WebSocketProvider(
        blockchain.ws_url,
        websocket_kwargs={"max_size": 32 * 1024 * 1024},
    )) as w3:
        chain_id = await w3.eth.chain_id
        logger.info("Connected: %s | chain_id=%d", await w3.is_connected(), chain_id)

        if chain_id != blockchain.chain_id:
            logger.error(
                "connected chain %d != configured chain %d — refusing to run",
                chain_id, blockchain.chain_id,
            )
            return

        persistence = ChainwatchPersistence(db, chain_id)

        tokens = await persistence.load_active_tokens()
        if not tokens:
            logger.error("No active tokens in DB. Seed tokens first.")
            return

        logger.info("Watching %d token(s): %s", len(tokens), [t.symbol for t in tokens])
        logger.info("Press Ctrl+C to stop")

        await asyncio.gather(
            ClaimWatcher(
                w3=w3,
                persistence=persistence,
                chain_id=chain_id,
                distributor_address='0x626300b270705aF188Aa1a0d7F7084D98B89e46d',
                stop_event=stop_event
            ).run(),
            *[
                watch_token(w3, persistence, chain_id, t.symbol, t.address, t.decimals, stop_event)
                for t in tokens
            ]
        )

    await db.close()
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())