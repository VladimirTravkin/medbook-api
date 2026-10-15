"""Schedule slot-related Pydantic schemas."""

import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SlotBase(BaseModel):
    """Shared slot fields."""

    start_time: datetime = Field(..., description="Slot start (timezone-aware)")
    end_time: datetime = Field(..., description="Slot end (timezone-aware)")

    @model_validator(mode="after")
    def check_time_range(self) -> "SlotBase":
        """Ensure end_time is strictly after start_time."""
        if self.end_time <= self.start_time:
            raise ValueError("Время окончания должно быть позже времени начала")
        return self


class SlotCreate(SlotBase):
    """Schema for creating a single slot manually."""


class SlotGenerateRequest(BaseModel):
    """Schema for bulk slot generation."""

    date_from: datetime = Field(..., description="First day to generate slots (inclusive)")
    date_to: datetime = Field(..., description="Last day to generate slots (inclusive)")
    work_day_start: time = Field(..., description="Working day start time")
    work_day_end: time = Field(..., description="Working day end time")
    slot_duration_minutes: int = Field(30, ge=5, le=240, description="Slot duration in minutes")
    break_start: time | None = Field(None, description="Optional break start time")
    break_end: time | None = Field(None, description="Optional break end time")
    weekdays: list[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5],
        description="Weekdays to generate (1=Mon, ..., 7=Sun)",
    )

    @model_validator(mode="after")
    def validate_ranges(self) -> "SlotGenerateRequest":
        """Validate date and time ranges."""
        if self.date_to < self.date_from:
            raise ValueError("date_to must be >= date_from")
        if self.work_day_end <= self.work_day_start:
            raise ValueError("work_day_end must be after work_day_start")
        if (self.break_start is None) != (self.break_end is None):
            raise ValueError("break_start and break_end must be set together")
        if self.break_start is not None and self.break_end is not None:
            if self.break_end <= self.break_start:
                raise ValueError("break_end must be after break_start")
        if not self.weekdays:
            raise ValueError("weekdays must not be empty")
        if any(d < 1 or d > 7 for d in self.weekdays):
            raise ValueError("weekdays must be in range 1..7")
        return self


class SlotGenerateResponse(BaseModel):
    """Result of bulk slot generation."""

    created: int = Field(..., description="Number of slots created")
    skipped: int = Field(..., description="Number of slots skipped (already exist)")


class SlotRead(SlotBase):
    """Schema for returning slot data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doctor_id: uuid.UUID
    is_booked: bool
    created_at: datetime
    updated_at: datetime
