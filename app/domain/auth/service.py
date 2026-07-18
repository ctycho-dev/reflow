# app/domain/auth/service.py
import secrets
from datetime import datetime, timezone

from redis.asyncio import Redis
from siwe import SiweMessage, generate_nonce, VerificationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.domain.auth.repo import AuthRepository
from app.domain.auth.schema import (
    AuthenticatedWallet,
    NonceResponse,
    VerifyResponse,
)
from app.domain.wallet.repo import WalletRepository
from app.exceptions.exceptions import UnauthorizedError, ValidationError
from app.utils.wallet_jwt import create_wallet_jwt

logger = get_logger(__name__)


class AuthService:
    def __init__(
        self,
        repo: AuthRepository,
        wallet_repo: WalletRepository,
    ):
        self.repo = repo
        self.wallet_repo = wallet_repo

    async def request_nonce(
        self,
        redis: Redis,
        *,
        address: str,
    ) -> NonceResponse:
        if not _is_valid_address(address):
            raise ValidationError(f"Invalid Ethereum address: {address}")

        nonce = generate_nonce()
        await self.repo.store_nonce(
            redis,
            address=address,
            nonce=nonce,
            ttl_seconds=settings.siwe.nonce_ttl_seconds,
        )
        return NonceResponse(nonce=nonce)

    async def verify(
        self,
        session: AsyncSession,
        redis: Redis,
        *,
        message: str,
        signature: str,
    ) -> tuple[VerifyResponse, str]:
        # 1. Parse
        try:
            siwe_message = SiweMessage.from_message(message)
        except Exception as e:
            raise UnauthorizedError(f"Malformed SIWE message: {e}") from e

        # 2. Structural validation
        if siwe_message.domain != settings.siwe.domain:
            raise UnauthorizedError(
                f"SIWE domain mismatch: expected {settings.siwe.domain}, "
                f"got {siwe_message.domain}"
            )

        if siwe_message.chain_id != 1:
            raise UnauthorizedError(
                f"Unsupported chain in SIWE message: {siwe_message.chain_id}"
            )

        if siwe_message.expiration_time:
            expiry = datetime.fromisoformat(
                siwe_message.expiration_time.replace("Z", "+00:00")
            )
            if expiry < datetime.now(timezone.utc):
                raise UnauthorizedError("SIWE message has expired")

        # 3. Signature verification (recovers signer + checks structural validity)
        try:
            siwe_message.verify(
                signature=signature,
                domain=settings.siwe.domain,
                nonce=siwe_message.nonce,
            )
        except VerificationError as e:
            raise UnauthorizedError(f"Signature verification failed: {e}") from e

        address = siwe_message.address.lower()

        # 4. Atomic nonce consume — replay defense.
        stored_nonce = await self.repo.consume_nonce(redis, address=address)
        if stored_nonce is None or stored_nonce != siwe_message.nonce:
            raise UnauthorizedError("Invalid or expired nonce")

        # 5. Upsert wallet
        await self.wallet_repo.upsert(
            session,
            chain_id=siwe_message.chain_id,
            address=address,
        )
        await session.commit()

        # 6. Mint JWT
        token = create_wallet_jwt(
            chain_id=siwe_message.chain_id,
            address=address,
        )

        logger.info(
            "siwe login success: wallet=%s chain=%s",
            address, siwe_message.chain_id,
        )

        wallet = AuthenticatedWallet(
            chain_id=siwe_message.chain_id,
            address=address,
        )
        return VerifyResponse(wallet=wallet), token


def _is_valid_address(address: str) -> bool:
    if not address.startswith("0x") or len(address) != 42:
        return False
    try:
        int(address[2:], 16)
        return True
    except ValueError:
        return False
