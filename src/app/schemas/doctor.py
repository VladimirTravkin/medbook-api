"""Doctor-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.schemas.specialization import SpecializationRead


class DoctorBase(BaseModel):
    """Shared doctor profile fields."""

    bio: str | None = Field(None, description="Short biography")
    experience_years: int | None = Field(None, ge=0, le=80, description="Years of practice")
    avatar_url: HttpUrl | None = Field(None, description="URL to the doctor's photo")


class DoctorCreate(DoctorBase):
    """Schema for creating a doctor (admin only).

    Creates both a User account (role=doctor) and a Doctor profile.
    """

    email: EmailStr = Field(..., description="Doctor's email (used for login)")
    password: str = Field(..., min_length=8, max_length=128, description="Initial password")
    full_name: str = Field(..., min_length=1, max_length=255, description="Doctor's full name")
    specialization_id: uuid.UUID = Field(..., description="Specialization ID")


class DoctorUpdate(BaseModel):
    """Schema for updating a doctor's profile (admin or the doctor themselves)."""

    bio: str | None = None
    experience_years: int | None = Field(None, ge=0, le=80)
    specialization_id: uuid.UUID | None = None
    avatar_url: HttpUrl | None = None


class DoctorRead(DoctorBase):
    """Schema for returning doctor data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    specialization_id: uuid.UUID
    full_name: str
    email: EmailStr
    specialization: SpecializationRead
    created_at: datetime
    updated_at: datetime


class DoctorShort(BaseModel):
    """Short doctor representation for lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    specialization: SpecializationRead
    experience_years: int | None
    avatar_url: HttpUrl | None
