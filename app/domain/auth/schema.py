# app/domain/auth/schema.py
from app.common.schema import CamelModel


class AuthenticatedWallet(CamelModel):
    """Identity surfaced by `get_current_wallet`. Backed by JWT in Phase 1.5."""
    chain_id: int
    address: str


class NonceRequest(CamelModel):
    address: str


class NonceResponse(CamelModel):
    nonce: str


class VerifyRequest(CamelModel):
    message: str
    signature: str


class VerifyResponse(CamelModel):
    """What the verify endpoint returns. JWT goes in an httpOnly cookie;
    the body just confirms identity."""
    wallet: AuthenticatedWallet