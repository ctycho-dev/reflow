from decimal import Decimal
from pydantic import BaseModel, field_validator


class TokenStatSchema(BaseModel):
    token: str
    name: str 
    symbol: str
    decimals: int
    color: str
    transfer_count: int
    total_volume_raw: str

    @field_validator("total_volume_raw", mode="before")
    @classmethod
    def coerce_to_str(cls, v) -> str:
        return format(Decimal(str(v)).normalize(), "f")


class ProtocolStatSchema(BaseModel):
    protocol: str
    protocol_name: str | None = None
    protocol_color: str | None = None 
    tokens: list[TokenStatSchema]