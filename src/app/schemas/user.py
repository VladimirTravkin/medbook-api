"""User-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Shared user fields."""

    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(..., min_length=8, max_length=128, description="Plain-text password")


class UserUpdate(BaseModel):
    """Schema for updating the current user's own profile."""

    full_name: str | None = Field(None, min_length=1, max_length=255)


class UserRead(UserBase):
    """Schema for returning user data (never includes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
