"""Specialization-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SpecializationBase(BaseModel):
    """Shared specialization fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Specialization name")
    description: str | None = Field(None, description="Optional description")


class SpecializationCreate(SpecializationBase):
    """Schema for creating a specialization (admin only)."""


class SpecializationUpdate(BaseModel):
    """Schema for updating a specialization (admin only)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None


class SpecializationRead(SpecializationBase):
    """Schema for returning specialization data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
