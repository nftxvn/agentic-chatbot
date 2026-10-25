"""Authentication dependencies shared by the AI HTTP routers."""

import logging
import secrets

from fastapi import Header, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


def assert_valid_bearer(authorization: str | None) -> str:
    """Validate an Authorization Bearer token using constant-time comparison."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format Authorization header tidak valid. Gunakan 'Bearer <token>'.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, settings.INTERNAL_API_TOKEN):
        logger.warning("Token tidak valid — akses ditolak")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid. Akses ditolak.",
        )

    return token


async def verify_webhook_token(
    authorization: str | None = Header(default=None),
) -> str:
    """Require a valid bearer token for webhook endpoints."""
    return assert_valid_bearer(authorization)


async def verify_chat_stream_token(
    authorization: str | None = Header(default=None),
) -> str | None:
    """Apply optional stream authentication, controlled by local configuration."""
    if not settings.CHAT_STREAM_REQUIRE_AUTH:
        return None

    return assert_valid_bearer(authorization)
