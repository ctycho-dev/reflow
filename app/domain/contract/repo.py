# app/domain/contract/repo.py
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.contract.model import ProtocolContract


class ContractRepository:
    async def get_protocol_addresses(
        self,
        session: AsyncSession,
        chain_id: int
    ) -> set[str]:
        stmt = select(ProtocolContract.address).where(ProtocolContract.chain_id == chain_id)
        result = await session.execute(stmt)
        return {row.lower() for row in result.scalars().all()}

    async def get_protocol_contracts_map(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> dict[str, dict]:
        result = await session.execute(
            select(ProtocolContract).where(ProtocolContract.chain_id == chain_id)
        )
        contracts = result.scalars().all()

        return {
            contract.address.lower(): {
                "address": contract.address.lower(),
                "protocol_slug": contract.protocol_slug,
                "protocol_name": contract.protocol_name,
                "protocol_color": contract.protocol_color,
                "label": contract.label,
            }
            for contract in contracts
        }
    
    async def list_distinct_protocols(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> Sequence[ProtocolContract]:
        stmt = (
            select(ProtocolContract)
            .where(ProtocolContract.chain_id == chain_id)
            .order_by(ProtocolContract.protocol_name)
        )

        res = await session.execute(stmt)
        return res.scalars().all()
    
    async def exists(
        self,
        session: AsyncSession,
        *,
        chain_id: int,
        address: str,
    ) -> bool:
        """Cheap existence check — returns True if the protocol contract is registered."""
        stmt = (
            select(ProtocolContract.address)
            .where(
                ProtocolContract.chain_id == chain_id,
                ProtocolContract.address == address.lower(),
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None