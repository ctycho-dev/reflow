# jobs/chainwatch/persistence.py
from web3 import AsyncWeb3

from app.database.connection import DatabaseManager
from app.domain.wallet.repo import WalletRepository
from app.domain.transfer.repo import TransferRepository
from app.domain.checkpoint.repo import CheckpointRepository
from app.domain.token.repo import TokenRepository
from app.domain.contract.repo import ContractRepository
from app.domain.processed_block.repo import ProcessedBlockRepository
from app.domain.campaign.reward_repo import RewardClaimRepository
from app.domain.token.model import Token
from worker.chainwatch.constants import CONFIRMATION_BLOCKS
from app.infrastructure.redis.pubsub import RedisPubSub
from app.infrastructure.redis.client import RedisClient
from app.domain.transfer.schema import TransferOutSchema
from app.core.logger import get_logger

logger = get_logger(__name__)


class ChainwatchPersistence:
    """DB + Redis persistence for the indexer. Holds the DatabaseManager and the
    chain_id (derived from the live connection at startup, Option B), so no
    function needs to import a singleton or a hardcoded CHAIN_ID."""

    def __init__(self, db: DatabaseManager, chain_id: int):
        self.db = db
        self.chain_id = chain_id
        self._redis_client: RedisClient | None = None
        self.wallet_repo = WalletRepository()
        self.transfer_repo = TransferRepository()
        self.checkpoint_repo = CheckpointRepository()
        self.token_repo = TokenRepository()
        self.contract_repo = ContractRepository()
        self.processed_block_repo = ProcessedBlockRepository()
        self.reward_claim_repo = RewardClaimRepository()

    def _get_redis_client(self) -> RedisClient:
        if self._redis_client is None:
            self._redis_client = RedisClient()
        return self._redis_client

    async def publish_transfer(self, payload: dict) -> None:
        schema = TransferOutSchema.model_validate(payload)
        json_data = schema.model_dump_json(by_alias=True)
        pubsub = RedisPubSub(
            client=self._get_redis_client().client,
            channel="transfers",
            object_id=str(payload["chain_id"]),
            client_id="chainwatch",
        )
        await pubsub.publish(json_data)

    async def load_tokens_map(self) -> dict[str, dict]:
        async with self.db.session_scope() as session:
            return await self.token_repo.get_tokens_map(session, self.chain_id)

    async def load_active_tokens(self) -> list[Token]:
        async with self.db.session_scope() as session:
            return await self.token_repo.get_active_tokens(session, self.chain_id)

    async def load_protocol_contracts_map(self) -> dict[str, dict]:
        async with self.db.session_scope() as session:
            return await self.contract_repo.get_protocol_contracts_map(session, self.chain_id)

    async def load_protocol_addresses(self) -> set[str]:
        async with self.db.session_scope() as session:
            return await self.contract_repo.get_protocol_addresses(session, self.chain_id)

    async def load_watched_wallets(self) -> set[str]:
        async with self.db.session_scope() as session:
            return await self.wallet_repo.get_watched_addresses(session, self.chain_id)

    async def get_start_block(self, symbol: str, token_address: str, w3: AsyncWeb3) -> int:
        async with self.db.session_scope() as session:
            last_block = await self.checkpoint_repo.get_last_block(
                session, token_address, self.chain_id
            )
        if last_block is not None:
            logger.info("[%s] Resuming from checkpoint block %d", symbol, last_block + 1)
            return last_block + 1
        current = (await w3.eth.block_number) - CONFIRMATION_BLOCKS
        logger.info("[%s] No checkpoint, starting from safe head=%d", symbol, current)
        return current

    async def persist_block(
        self, symbol, token_address, block_number, block_hash, parent_hash, transfers,
    ) -> None:
        async with self.db.session_scope() as session:
            async with session.begin():
                await self.transfer_repo.bulk_insert_ignore(session, transfers)
                await self.processed_block_repo.insert_ignore(
                    session, token_address, self.chain_id, block_number, block_hash, parent_hash,
                )
                await self.checkpoint_repo.upsert(session, token_address, self.chain_id, block_number)
        logger.info("[%s] block %d | %d transfers", symbol, block_number, len(transfers))

    async def persist_checkpoint(
        self, symbol, token_address, block_number, block_hash, parent_hash,
    ) -> None:
        async with self.db.session_scope() as session:
            async with session.begin():
                await self.processed_block_repo.insert_ignore(
                    session, token_address, self.chain_id, block_number, block_hash, parent_hash,
                )
                await self.checkpoint_repo.upsert(session, token_address, self.chain_id, block_number)
        logger.debug("[%s] checkpoint -> block %d (no relevant transfers)", symbol, block_number)

    async def mark_claimed(
        self, *, campaign_id: int, wallet_address: str,
        claimed_ts: int, claim_tx_hash: bytes,
    ) -> bool:
        async with self.db.session_scope() as session:
            async with session.begin():
                updated = await self.reward_claim_repo.mark_claimed(
                    session,
                    campaign_id=campaign_id,
                    wallet_address=wallet_address,
                    claimed_ts=claimed_ts,
                    claim_tx_hash=claim_tx_hash,
                )
        return updated


def build_transfer_payload(transfer: dict, token_meta: dict, counterparty_meta: dict) -> dict:
    """Pure function — no DB, no chain_id state. Stays module-level."""
    return {
        "chain_id": transfer["chain_id"],
        "tx_hash": transfer["tx_hash"],
        "log_index": transfer["log_index"],
        "block_number": transfer["block_number"],
        "block_timestamp": transfer["block_timestamp"],
        "from_address": transfer["from_address"],
        "to_address": transfer["to_address"],
        "amount": transfer["amount"],
        "token": {
            "address": token_meta["address"],
            "symbol": token_meta["symbol"],
            "name": token_meta["name"],
            "decimals": token_meta["decimals"],
            "color": token_meta["color"],
        },
        "counterparty": {
            "address": counterparty_meta["address"],
            "protocol": {
                "slug": counterparty_meta["protocol_slug"],
                "name": counterparty_meta["protocol_name"],
                "color": counterparty_meta["protocol_color"],
            },
            "label": counterparty_meta["label"],
        },
    }