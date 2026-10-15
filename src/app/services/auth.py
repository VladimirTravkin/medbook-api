"""Authentication service: registration, login, token refresh and logout."""

import uuid

from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.redis import get_redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_jti,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest, TokenPair


class AuthService:
    """Service handling user authentication and token lifecycle."""

    def __init__(self, session: AsyncSession, redis: Redis | None = None) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.redis = redis or get_redis_client()

    # ============================================
    # Redis: refresh token storage
    # ============================================

    @staticmethod
    def _refresh_key(user_id: uuid.UUID, jti: str) -> str:
        """Build Redis key for a refresh token."""
        return f"refresh:{user_id}:{jti}"

    async def _store_refresh_token(self, user_id: uuid.UUID, jti: str) -> None:
        """Persist refresh token jti in Redis with TTL matching token lifetime."""
        key = self._refresh_key(user_id, jti)
        ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        await self.redis.set(key, "1", ex=ttl_seconds)

    async def _is_refresh_token_valid(self, user_id: uuid.UUID, jti: str) -> bool:
        """Check whether refresh token jti is still stored in Redis."""
        key = self._refresh_key(user_id, jti)
        return await self.redis.exists(key) == 1

    async def _revoke_refresh_token(self, user_id: uuid.UUID, jti: str) -> None:
        """Remove refresh token jti from Redis (revocation)."""
        key = self._refresh_key(user_id, jti)
        await self.redis.delete(key)

    # ============================================
    # Token helpers
    # ============================================

    async def _issue_token_pair(self, user: User) -> TokenPair:
        """Create a fresh access + refresh token pair and store refresh jti."""
        subject = str(user.id)
        access = create_access_token(subject, extra_claims={"role": user.role.value})
        refresh = create_refresh_token(subject)
        refresh_jti = get_token_jti(refresh)
        if refresh_jti is None:
            raise UnauthorizedError("Не удалось создать refresh-токен")
        await self._store_refresh_token(user.id, refresh_jti)
        return TokenPair(access_token=access, refresh_token=refresh)

    # ============================================
    # Public API
    # ============================================

    async def register(self, data: RegisterRequest) -> User:
        """Register a new patient account."""
        email = data.email.lower()
        if await self.users.email_exists(email):
            raise ConflictError("Пользователь с таким email уже существует")

        user = await self.users.create(
            email=email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            role=UserRole.PATIENT,
            is_active=True,
        )
        await self.session.commit()
        return user

    async def login(self, email: str, password: str) -> TokenPair:
        """Authenticate a user and return a token pair."""
        user = await self.users.get_by_email(email.lower())
        if user is None or not verify_password(password, user.password_hash):
            # Same error for both cases — do not leak which one failed
            raise UnauthorizedError("Неверный email или пароль")

        if not user.is_active:
            raise UnauthorizedError("Учётная запись деактивирована")

        return await self._issue_token_pair(user)

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Rotate a refresh token: validate, revoke the old one, issue a new pair."""
        try:
            payload = decode_token(refresh_token)
        except JWTError as exc:
            raise UnauthorizedError("Недействительный refresh-токен") from exc

        if payload.get("type") != "refresh":
            raise UnauthorizedError("Неверный тип токена")

        subject = payload.get("sub")
        jti = payload.get("jti")
        if not subject or not jti:
            raise UnauthorizedError("Некорректный refresh-токен")

        try:
            user_id = uuid.UUID(subject)
        except ValueError as exc:
            raise UnauthorizedError("Некорректный subject токена") from exc

        # Token must still be present in Redis (not revoked)
        if not await self._is_refresh_token_valid(user_id, str(jti)):
            raise UnauthorizedError("Refresh-токен отозван или истёк")

        user = await self.users.get(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Пользователь не найден или деактивирован")

        # Rotate: revoke old jti, issue new pair
        await self._revoke_refresh_token(user_id, str(jti))
        return await self._issue_token_pair(user)

    async def logout(self, refresh_token: str) -> None:
        """Revoke a refresh token. Idempotent — no error if token is invalid."""
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            # Even an invalid/expired token — try to extract jti without verification
            jti = get_token_jti(refresh_token)
            if jti is None:
                return
            # Cannot determine user_id reliably; nothing to do
            return

        subject = payload.get("sub")
        jti = payload.get("jti")
        if not subject or not jti:
            return

        try:
            user_id = uuid.UUID(subject)
        except ValueError:
            return

        await self._revoke_refresh_token(user_id, str(jti))
