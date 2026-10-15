"""Password hashing and JWT token utilities."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import settings

# ============================================
# Password hashing
# ============================================

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plain-text password using the recommended algorithm (argon2)."""
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored hash."""
    return _password_hash.verify(plain_password, hashed_password)


# ============================================
# JWT
# ============================================

TokenType = Literal["access", "refresh"]


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT with standard claims.

    Standard claims:
        sub  - subject (user id)
        exp  - expiration timestamp
        iat  - issued at
        jti  - unique token id (used for refresh token revocation)
        type - token type ("access" or "refresh")
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a short-lived access token."""
    return _create_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims=extra_claims,
    )


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh token."""
    return _create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT.

    Raises:
        JWTError: if the token is invalid, expired or has a bad signature.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def get_token_jti(token: str) -> str | None:
    """Extract the `jti` claim from a token without validating its signature.

    Used only for logout: even if the token is expired we still want to
    remove its `jti` from Redis.
    """
    try:
        payload = jwt.get_unverified_claims(token)
    except JWTError:
        return None
    jti = payload.get("jti")
    return str(jti) if jti else None


__all__ = [
    "JWTError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_token_jti",
    "hash_password",
    "verify_password",
]
