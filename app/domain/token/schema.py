# app/domain/token/schema.py
from app.common.schema import CamelModel


class TokenOutSchema(CamelModel):
    address: str
    symbol: str
    name: str
    decimals: int
    color: str