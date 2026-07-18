# app/domain/enrollment/schema.py
from datetime import datetime
from decimal import Decimal
from pydantic import field_serializer
from app.common.schema import CamelModel
from app.domain.campaign.schema import CampaignOutSchema


class EnrollmentOutSchema(CamelModel):
    id: int
    wallet_chain_id: int
    wallet_address: str
    campaign_id: int
    total_volume: Decimal
    qualified_at: datetime | None
    created_at: datetime

    @field_serializer("total_volume")
    def _bignum_as_int_string(self, v: Decimal) -> str:
        return format(v, "f")


class LeaderboardEntrySchema(CamelModel):
    rank: int
    wallet_address: str
    total_volume: Decimal
    qualified: bool

    @field_serializer("total_volume")
    def _bignum_as_int_string(self, v: Decimal) -> str:
        return format(v, "f")


class CampaignEligibilitySchema(CamelModel):
    """One campaign's view of a wallet's eligibility status."""
    campaign: CampaignOutSchema
    enrolled: bool
    qualified: bool
    total_volume: Decimal
    progress: float

    @field_serializer("total_volume")
    def _bignum_as_int_string(self, v: Decimal) -> str:
        return format(v, "f")


class WalletEligibilitySchema(CamelModel):
    """Wallet status across all currently relevant campaigns."""
    wallet_address: str
    chain_id: int
    campaigns: list[CampaignEligibilitySchema]
