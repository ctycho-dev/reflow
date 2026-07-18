# app/domain/transfer/repository.py
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from sqlalchemy import func, or_, and_

from app.common.base_repository import BaseRepository
from app.domain.transfer.model import Transfer
from app.domain.token.model import Token
from app.exceptions.exceptions import DatabaseError
from app.domain.contract.model import ProtocolContract


class TransferRepository(BaseRepository[Transfer]):
    def __init__(self) -> None:
        super().__init__(Transfer)

    async def bulk_insert_ignore(
        self,
        session: AsyncSession,
        transfers: list[dict],
    ) -> None:
        """
        Idempotent batch insert. Skips rows conflicting on (tx_hash, log_index).
        Returns count of actually inserted rows (0 for full duplicate batches).
        """
        if not transfers:
            return

        try:
            stmt = (
                pg_insert(Transfer)
                .values(transfers)
                .on_conflict_do_nothing(index_elements=["chain_id", "tx_hash", "log_index"])
            )
            await session.execute(stmt)
        except Exception as e:
            raise DatabaseError(f"Failed to bulk insert transfers: {e}") from e

    async def get_recent(
        self,
        session: AsyncSession,
        chain_id: int,
        token: str | None = None,
        protocol: str | None = None,
        limit: int = 100,
    ) -> list[tuple]:
        stmt = (
            select(
                Transfer,
                Token,
                ProtocolContract,
            )
            .join(
                Token,
                (Transfer.token == Token.address)
                & (Transfer.chain_id == Token.chain_id),
            )
            .join(
                ProtocolContract,
                (Transfer.chain_id == ProtocolContract.chain_id)
                & (
                    (Transfer.to_address == ProtocolContract.address)
                    | (Transfer.from_address == ProtocolContract.address)
                ),
            )
            .where(Transfer.chain_id == chain_id)
        )

        if token:
            stmt = stmt.where(Transfer.token == token)

        if protocol:
            stmt = stmt.where(ProtocolContract.protocol_slug == protocol)

        stmt = stmt.order_by(
            desc(Transfer.block_number),
            desc(Transfer.log_index),
        ).limit(limit)

        result = await session.execute(stmt)
        return list(result.all())
    
    async def sum_volume_for_wallet(
        self,
        session: AsyncSession,
        *,
        chain_id: int,
        token_address: str,
        wallet_address: str,
        start_ts: datetime,
        end_ts: datetime,
        target_contract_address: str | None = None,
    ) -> Decimal:
        """
        Sum of transfer amounts where the wallet was sender OR receiver,
        within the campaign window, on the specified token and chain.

        If target_contract_address is provided, restrict to transfers where the
        target contract is the counterparty (the other side of the transfer).
        Otherwise, count every relevant transfer the wallet participated in.

        Returns Decimal('0') if no matching transfers exist.
        """
        try:
            wallet_predicate = or_(
                Transfer.from_address == wallet_address,
                Transfer.to_address == wallet_address,
            )

            conditions = [
                Transfer.chain_id == chain_id,
                Transfer.token == token_address,
                Transfer.block_timestamp >= start_ts,
                Transfer.block_timestamp <= end_ts,
                wallet_predicate,
            ]

            if target_contract_address is not None:
                conditions.append(
                    or_(
                        Transfer.from_address == target_contract_address,
                        Transfer.to_address == target_contract_address,
                    )
                )

            stmt = select(
                func.coalesce(func.sum(Transfer.amount), 0)
            ).where(and_(*conditions))

            result = await session.execute(stmt)
            total = result.scalar_one()
            return Decimal(total)
        except Exception as e:
            raise DatabaseError(
                f"Failed to aggregate volume for wallet {wallet_address}: {e}"
            ) from e
