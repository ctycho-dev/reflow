from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from eth_utils import is_address

from app.domain.transfer.repo import TransferRepository
from app.domain.transfer.schema import TransferOutSchema
from app.core.logger import get_logger

logger = get_logger(__name__)


class TransferService:
    def __init__(self, repo: TransferRepository):
        self.repo = repo

    def _validate_address(self, address: str | None) -> str | None:
        if address is None:
            return None
        if not is_address(address):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid EVM address")
        return address.lower()

    async def get_recent(
        self,
        session: AsyncSession,
        chain_id: int,
        token: str | None,
        protocol: str | None,
        limit: int,
    ) -> list[TransferOutSchema]:
        safe_token = self._validate_address(token)

        rows = await self.repo.get_recent(
            session,
            chain_id=chain_id,
            token=safe_token,
            protocol=protocol,
            limit=limit,
        )

        result = []
        for transfer_obj, token_obj, contract_obj in rows:
            # Same counterparty resolution rule as watcher: to_address wins
            counterparty_address = (
                contract_obj.address
                if transfer_obj.to_address.lower() == contract_obj.address.lower()
                else contract_obj.address
            )

            data = {
                "chain_id": transfer_obj.chain_id,
                "tx_hash": transfer_obj.tx_hash,
                "log_index": transfer_obj.log_index,
                "block_number": transfer_obj.block_number,
                "block_timestamp": transfer_obj.block_timestamp,
                "from_address": transfer_obj.from_address,
                "to_address": transfer_obj.to_address,
                "amount": transfer_obj.amount,
                "token": {
                    "address": token_obj.address.lower(),
                    "symbol": token_obj.symbol,
                    "name": token_obj.name,
                    "decimals": token_obj.decimals,
                    "color": token_obj.color,
                },
                "counterparty": {
                    "address": counterparty_address.lower(),
                    "protocol": {
                        "slug": contract_obj.protocol_slug,
                        "name": contract_obj.protocol_name,
                        "color": contract_obj.protocol_color,
                    },
                    "label": contract_obj.label,
                },
            }
            result.append(TransferOutSchema.model_validate(data))

        return result