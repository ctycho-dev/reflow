# app/domain/campaign/schema.py
from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator, field_serializer

from app.common.schema import CamelModel
from app.core.constants import ETH_ADDRESS_REGEX


class CampaignCreateSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)

    chain_id: int = Field(..., gt=0, description="EVM chain ID")
    token_address: str = Field(..., pattern=ETH_ADDRESS_REGEX)
    target_contract_address: str | None = Field(
        None,
        pattern=ETH_ADDRESS_REGEX,
        description="Optional — if set, only transfers to this contract count",
    )

    min_total_volume: Decimal = Field(
        ...,
        gt=0,
        description="Cumulative qualifying volume threshold, in token base units",
    )
    reward_amount: Decimal = Field(
        ...,
        gt=0,
        description="Flat reward credited per qualifying wallet",
    )

    duration_days: int = Field(..., gt=0, le=365)
    starts_at: datetime = Field(..., description="UTC start timestamp")
    max_recipients: int = Field(
        ...,
        gt=0,
        description="Maximum number of wallets that can enroll",
    )

    @field_validator("token_address", "target_contract_address")
    @classmethod
    def _addresses_lower(cls, v: str | None) -> str | None:
        return v.lower() if v else v


class CampaignOutSchema(CamelModel):
    id: int
    name: str
    description: str | None

    chain_id: int
    token_address: str
    target_contract_address: str | None

    min_total_volume: Decimal
    reward_amount: Decimal

    duration_days: int
    starts_at: datetime
    ends_at: datetime

    max_recipients: int
    enrolled_count: int

    created_at: datetime

    @field_serializer("min_total_volume", "reward_amount")
    def _bignum_as_int_string(self, v: Decimal) -> str:
        return format(v, "f")


class ClaimProofSchema(CamelModel):
    campaign_id: int
    wallet_address: str
    amount: str          # wei as string (matches your Decimal->string serializer convention)
    leaf_index: int
    proof: list[str]     # 0x-prefixed sibling hashes, ready for the contract
    claimed: bool        # convenience: whether claimed_at is set
