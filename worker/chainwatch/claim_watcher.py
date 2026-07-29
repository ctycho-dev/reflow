import asyncio
import time
from collections import defaultdict

from web3 import AsyncWeb3

from worker.chainwatch.constants import (
    DISTRIBUTOR_ABI,
    POLL_INTERVAL,
    BACKFILL_CHUNK_SIZE,
    CONFIRMATION_BLOCKS,
)
from worker.chainwatch.parser import parse_raw_event, log_event
from worker.chainwatch.persistence import ChainwatchPersistence
from app.core.logger import get_logger

REFRESH_INTERVAL_SECONDS = 60

logger = get_logger(__name__)


class ClaimWatcher:
    """
    Watches one ERC-20 token's Transfer events: backfill to safe head, then live
    poll. Holds w3 + persistence + chain_id + per-token metadata, so the internal
    steps use self.* rather than threading everything through call signatures.
    """

    def __init__(
        self,
        w3: AsyncWeb3,
        persistence: ChainwatchPersistence,
        chain_id: int,
        distributor_address: str,
        stop_event: asyncio.Event,
    ):
        self.w3 = w3
        self.persistence = persistence
        self.chain_id = chain_id
        self.symbol = "RewardDistributor"
        self.contract_address = AsyncWeb3.to_checksum_address(distributor_address)
        self.address = distributor_address.lower() # for checkpoint repo calls
        self.stop_event = stop_event
        self.contract = w3.eth.contract(address=self.contract_address, abi=DISTRIBUTOR_ABI)

    async def _fetch_block_meta(self, block_numbers: list[int]) -> dict[int, dict]:
        blocks = await asyncio.gather(
            *[self.w3.eth.get_block(bn) for bn in block_numbers]
        )
        return {
            b["number"]: {
                "timestamp": b["timestamp"],
                "hash": b["hash"].hex(),
                "parent_hash": b["parentHash"].hex(),
            }
            for b in blocks
        }

    async def _process_relevant_events(
        self, relevant: list[dict], block_meta: dict[int, dict]
    ) -> set[int]:
        by_block: dict[int, list[dict]] = defaultdict(list)
        for e in relevant:
            by_block[e["blockNumber"]].append(e)

        persisted_blocks: set[int] = set()

        for block_number in sorted(by_block.keys()):
            meta = block_meta[block_number]

            for e in by_block[block_number]:
                campaign_id = int(e["args"]["campaignId"])
                wallet = e["args"]["wallet"].lower()
                tx_hash = bytes(e["transactionHash"])

                updated = await self.persistence.mark_claimed(
                    campaign_id=campaign_id,
                    wallet_address=wallet,
                    claimed_ts=meta["timestamp"],
                    claim_tx_hash=tx_hash,
                )
                logger.info(
                    "[%s] Claimed: campaign=%d wallet=%s tx=%s%s",
                    self.symbol, campaign_id, wallet, tx_hash.hex(),
                    "" if updated else " (no matching unclaimed row)",
                )

            # checkpoint this block like TokenWatcher does
            await self.persistence.persist_checkpoint(
                self.symbol, self.address, block_number,
                meta["hash"], meta["parent_hash"],
            )
            persisted_blocks.add(block_number)

        return persisted_blocks

    async def _process_chunk(self, cursor: int, end: int, label: str = "chunk") -> None:
        raw_logs = await self.contract.events.Claimed.get_logs(
            from_block=cursor, to_block=end
        )
        relevant = raw_logs
        logger.debug("[%s] %s %s→%s | %d raw | %d relevant",
                     self.symbol, label, cursor, end, len(raw_logs), len(relevant))

        block_numbers_to_fetch = {cursor, end}
        if relevant:
            block_numbers_to_fetch.update(e["blockNumber"] for e in relevant)
        block_meta = await self._fetch_block_meta(sorted(block_numbers_to_fetch))

        persisted: set[int] = set()
        if relevant:
            persisted = await self._process_relevant_events(relevant, block_meta)

        if end not in persisted:
            end_meta = block_meta[end]
            await self.persistence.persist_checkpoint(
                self.symbol, self.address, end,
                end_meta["hash"], end_meta["parent_hash"],
            )

    async def _backfill(self, from_block: int, to_block: int) -> None:
        cursor = from_block
        chunks_done = 0
        while cursor <= to_block and not self.stop_event.is_set():
            end = min(cursor + BACKFILL_CHUNK_SIZE - 1, to_block)
            await self._process_chunk(cursor, end, label="backfill")
            chunks_done += 1
            cursor = end + 1
            await asyncio.sleep(3)
        logger.info("[%s] Backfill done | %d chunks", self.symbol, chunks_done)

    async def _poll_live(self, cursor: int) -> None:
        logger.info("[%s] Live polling from block %d", self.symbol, cursor)
        last_refresh = time.monotonic()
        head = await self.w3.eth.block_number
        safe_head = head - CONFIRMATION_BLOCKS

        while not self.stop_event.is_set():
            try:
                if cursor > safe_head:
                    await asyncio.sleep(POLL_INTERVAL)
                    head = await self.w3.eth.block_number
                    safe_head = head - CONFIRMATION_BLOCKS
                    continue

                end = min(cursor + BACKFILL_CHUNK_SIZE - 1, safe_head)
                await self._process_chunk(cursor, end, label="live")
                cursor = end + 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("[%s] %s: %s", self.symbol, type(e).__name__, e)
                await asyncio.sleep(POLL_INTERVAL)
                head = await self.w3.eth.block_number
                safe_head = head - CONFIRMATION_BLOCKS

        logger.info("[%s] Shutting down. Last cursor: %d", self.symbol, cursor - 1)

    async def run(self) -> None:
        from_block = await self.persistence.get_start_block(self.symbol, self.address, self.w3)
        current_block = await self.w3.eth.block_number
        safe_head = current_block - CONFIRMATION_BLOCKS

        if from_block > safe_head:
            logger.info("[%s] Clamping start block %d → %d (confirmation window)",
                        self.symbol, from_block, safe_head)
            from_block = safe_head

        logger.info("[%s] from_block=%d safe_head=%d delta=%d",
                    self.symbol, from_block, safe_head, safe_head - from_block)

        if from_block < safe_head:
            logger.info("[%s] Backfilling %d→%d...", self.symbol, from_block, safe_head)
            await self._backfill(from_block, safe_head)
            logger.info("[%s] Backfill complete.", self.symbol)
        else:
            logger.debug("[%s] At safe head, skipping backfill.", self.symbol)

        if self.stop_event.is_set():
            return

        live_cursor = safe_head + 1 if from_block < safe_head else from_block + 1
        await self._poll_live(live_cursor)


async def watch_token(
    w3: AsyncWeb3,
    persistence: ChainwatchPersistence,
    chain_id: int,
    symbol: str,
    address: str,
    decimals: int,
    stop_event: asyncio.Event,
) -> None:
    """Thin wrapper so main's gather call stays unchanged in shape."""
    watcher = ClaimWatcher(w3, persistence, chain_id, symbol, address, decimals, stop_event)
    await watcher.run()
