import asyncio
import time
from collections import defaultdict

from web3 import AsyncWeb3

from worker.chainwatch.constants import (
    ERC20_ABI,
    POLL_INTERVAL,
    BACKFILL_CHUNK_SIZE,
    CONFIRMATION_BLOCKS,
)
from worker.chainwatch.parser import parse_raw_event, log_event
from worker.chainwatch.persistence import ChainwatchPersistence, build_transfer_payload
from app.core.logger import get_logger

REFRESH_INTERVAL_SECONDS = 60

logger = get_logger(__name__)


class TokenWatcher:
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
        symbol: str,
        address: str,
        decimals: int,
        stop_event: asyncio.Event,
    ):
        self.w3 = w3
        self.persistence = persistence
        self.chain_id = chain_id
        self.symbol = symbol
        self.token_address = AsyncWeb3.to_checksum_address(address)
        self.address = address  # lowercase/original for repo calls
        self.decimals = decimals
        self.stop_event = stop_event
        self.contract = w3.eth.contract(address=self.token_address, abi=ERC20_ABI)

        # metadata maps, loaded once and refreshed periodically during live poll
        self.protocol_contracts: dict[str, dict] = {}
        self.tokens_map: dict[str, dict] = {}

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
            db_transfers: list[dict] = []
            redis_payloads: list[dict] = []

            for e in by_block[block_number]:
                t = parse_raw_event(e, meta["timestamp"], self.chain_id)

                to_addr = t["to_address"].lower()
                from_addr = t["from_address"].lower()

                counterparty_meta = (
                    self.protocol_contracts.get(to_addr)
                    or self.protocol_contracts.get(from_addr)
                )
                token_meta = self.tokens_map.get(t["token"].lower())

                if not token_meta:
                    logger.debug("[%s] skip — missing token metadata for %s", self.symbol, t["token"])
                    continue
                if not counterparty_meta:
                    logger.debug("[%s] skip — no counterparty match (from=%s to=%s)", self.symbol, from_addr, to_addr)
                    continue

                payload = build_transfer_payload(
                    transfer=t,
                    token_meta=token_meta,
                    counterparty_meta=counterparty_meta,
                )
                db_transfers.append(t)
                redis_payloads.append(payload)
                log_event(e, self.symbol, self.decimals)

            if db_transfers:
                await self.persistence.persist_block(
                    self.symbol, self.token_address, block_number,
                    meta["hash"], meta["parent_hash"], db_transfers,
                )
                persisted_blocks.add(block_number)
                for payload in redis_payloads:
                    await self.persistence.publish_transfer(payload)

        return persisted_blocks

    async def _process_chunk(self, cursor: int, end: int, label: str = "chunk") -> None:
        raw_logs = await self.contract.events.Transfer.get_logs(
            from_block=cursor, to_block=end
        )
        relevant = [
            e for e in raw_logs
            if e["args"]["from"].lower() in self.protocol_contracts
            or e["args"]["to"].lower() in self.protocol_contracts
        ]
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
                self.symbol, self.token_address, end,
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
            if time.monotonic() - last_refresh > REFRESH_INTERVAL_SECONDS:
                self.protocol_contracts = await self.persistence.load_protocol_contracts_map()
                self.tokens_map = await self.persistence.load_tokens_map()
                last_refresh = time.monotonic()
                logger.info("[%s] refreshed maps", self.symbol)
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
        # metadata maps, loaded once at start
        self.protocol_contracts = await self.persistence.load_protocol_contracts_map()
        self.tokens_map = await self.persistence.load_tokens_map()

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
    watcher = TokenWatcher(w3, persistence, chain_id, symbol, address, decimals, stop_event)
    await watcher.run()