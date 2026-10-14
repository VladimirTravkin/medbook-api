"""User repository with user-specific queries."""

from sqlalchemy import select

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model."""

    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email (case-insensitive)."""
        stmt = select(User).where(User.email == email.lower()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check whether a user with given email already exists."""
        stmt = select(User.id).where(User.email == email.lower()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_by_role(
        self,
        role: UserRole,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> list[User]:
        """List users with a specific role."""
        stmt = (
            select(User)
            .where(User.role == role)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
