# app/domain/transfer/schema.py
from datetime import datetime
from decimal import Decimal
from pydantic import Field, field_validator
from app.common.schema import CamelModel


class ProtocolSchema(CamelModel):
    slug: str
    name: str
    color: str


class TokenMetaSchema(CamelModel):
    address: str
    symbol: str
    name: str
    decimals: int
    color: str


class CounterpartySchema(CamelModel):
    address: str
    protocol: ProtocolSchema
    label: str


class TransferOutSchema(CamelModel):
    chain_id: int
    tx_hash: str
    log_index: int
    block_number: int
    block_timestamp: datetime
    from_address: str
    to_address: str
    amount_raw: str = Field(validation_alias="amount")
    token: TokenMetaSchema
    counterparty: CounterpartySchema

    @field_validator("amount_raw", mode="before")
    @classmethod
    def coerce_to_str(cls, v) -> str:
        return format(Decimal(str(v)).normalize(), "f")
