"""Appointment-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.appointment import AppointmentStatus
from app.schemas.slot import SlotRead


class AppointmentCreate(BaseModel):
    """Schema for creating a new appointment."""

    slot_id: uuid.UUID = Field(..., description="ID of the slot to book")
    notes: str | None = Field(None, max_length=1000, description="Optional notes")


class AppointmentStatusUpdate(BaseModel):
    """Schema for updating appointment status (doctor/admin)."""

    status: AppointmentStatus = Field(..., description="New appointment status")


class AppointmentRead(BaseModel):
    """Schema for returning appointment data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    slot_id: uuid.UUID
    status: AppointmentStatus
    notes: str | None
    slot: SlotRead
    created_at: datetime
    updated_at: datetime


class AppointmentDetail(BaseModel):
    """Extended appointment view with patient and doctor info."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    slot_id: uuid.UUID
    status: AppointmentStatus
    notes: str | None
    slot: SlotRead
    patient_full_name: str
    patient_email: str
    doctor_full_name: str
    created_at: datetime
    updated_at: datetime
