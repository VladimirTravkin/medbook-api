"""SQLAlchemy models package.

This module imports all models so that they are registered in
Base.metadata before Alembic autogenerate runs.
"""

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.schedule_slot import ScheduleSlot
from app.models.specialization import Specialization
from app.models.user import User, UserRole

__all__ = [
    "Appointment",
    "AppointmentStatus",
    "Doctor",
    "ScheduleSlot",
    "Specialization",
    "User",
    "UserRole",
]
