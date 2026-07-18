# # app/api/dependencies/auth.py
# from fastapi import (
#     HTTPException,
#     status,
#     Request,
#     Depends
# )
# # from sqlalchemy.ext.asyncio import AsyncSession
# # from app.api.dependencies.db import get_db
# # from app.utils.oauth2 import verify_access_token
# from app.domain.auth.schema import AuthenticatedWallet


# async def get_current_wallet(
#     # _: None = Depends(verify_api_key),
#     # db: AsyncSession = Depends(get_db),
#     # Phase 1: hardcoded. Phase 1.5: parse from JWT.
#     # TODO(siwe): replace with JWT-extracted wallet
# ) -> AuthenticatedWallet:
#     return AuthenticatedWallet(
#         chain_id=1,
#         address="0x0000000000000000000000000000000000000001",
#     )


# app/api/dependencies/auth.py
from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_session
from app.core.config import settings
from app.domain.auth.schema import AuthenticatedWallet
from app.exceptions.exceptions import UnauthorizedError
from app.utils.wallet_jwt import decode_wallet_jwt


async def get_current_wallet(
    reflow_access_token: str | None = Cookie(None, alias="reflow_access_token"),
) -> AuthenticatedWallet:
    """
    Resolve the authenticated wallet from the JWT in the httpOnly cookie.

    Mirrors the existing get_current_user pattern. Cookie name configurable
    via settings.siwe.jwt_cookie_name.
    """
    if not reflow_access_token:
        raise UnauthorizedError("Not authenticated")

    payload = decode_wallet_jwt(reflow_access_token)

    return AuthenticatedWallet(
        chain_id=payload["chainId"],
        address=payload["sub"],
    )