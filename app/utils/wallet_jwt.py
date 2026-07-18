# app/utils/wallet_jwt.py
"""
JWT issuance + verification for wallet-authenticated sessions.

Separate from `oauth2.py` (which encodes user_id for the Web2-style auth)
because the wallet flow has a different claim shape: subject is the wallet
address, not a user_id, and chain_id is required.
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings
from app.exceptions.exceptions import UnauthorizedError


def create_wallet_jwt(*, chain_id: int, address: str) -> str:
    """
    Mint a JWT for an authenticated wallet.

    Claims:
      sub      → wallet address (lowercase)
      chainId  → EIP-155 chain id
      iat      → issued-at (UTC)
      exp      → expiry (UTC)
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": address.lower(),
        "chainId": chain_id,
        "iat": now,
        "exp": now + timedelta(hours=settings.siwe.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt.secret_key, algorithm=settings.jwt.algorithm)


def decode_wallet_jwt(token: str) -> dict:
    """
    Decode + validate a wallet JWT. Raises UnauthorizedError on any failure.
    """
    try:
        payload = jwt.decode(token, settings.jwt.secret_key, algorithms=[settings.jwt.algorithm])
    except JWTError as e:
        raise UnauthorizedError("Invalid or expired session") from e

    if not payload.get("sub") or not payload.get("chainId"):
        raise UnauthorizedError("Malformed session token")

    return payload