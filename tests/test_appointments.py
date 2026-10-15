"""Tests for appointment endpoints."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.schedule_slot import ScheduleSlot

# ============================================
# Create (patient)
# ============================================


async def test_create_appointment_success(
    client: AsyncClient,
    auth_headers: dict[str, str],
    future_slot: ScheduleSlot,
) -> None:
    """Patient books a free slot."""
    response = await client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={"slot_id": str(future_slot.id), "notes": "Болит голова"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["slot_id"] == str(future_slot.id)
    assert data["status"] == "pending"
    assert data["notes"] == "Болит голова"


async def test_create_appointment_past_slot(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
    test_doctor: Doctor,
) -> None:
    """Booking a slot in the past returns 400."""
    start = datetime.now(UTC) - timedelta(days=1)
    end = start + timedelta(minutes=30)
    slot = ScheduleSlot(
        doctor_id=test_doctor.id,
        start_time=start,
        end_time=end,
        is_booked=False,
    )
    db_session.add(slot)
    await db_session.flush()

    response = await client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={"slot_id": str(slot.id)},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


async def test_create_appointment_booked_slot(
    client: AsyncClient,
    auth_headers: dict[str, str],
    booked_slot: ScheduleSlot,
) -> None:
    """Booking an already booked slot returns 409."""
    response = await client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={"slot_id": str(booked_slot.id)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_create_appointment_doctor_forbidden(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    future_slot: ScheduleSlot,
) -> None:
    """Doctor cannot book appointments."""
    response = await client.post(
        "/api/v1/appointments",
        headers=doctor_headers,
        json={"slot_id": str(future_slot.id)},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_create_appointment_patient_overlap(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_doctor: Doctor,
    booked_slot: ScheduleSlot,
    db_session,
) -> None:
    """Patient cannot book two overlapping appointments.

    booked_slot already exists at +3 days, 30 min.
    Create another slot with same time range for the same doctor,
    and try to book it.
    """
    overlap_slot = ScheduleSlot(
        doctor_id=test_doctor.id,
        start_time=booked_slot.start_time,
        end_time=booked_slot.end_time,
        is_booked=False,
    )
    db_session.add(overlap_slot)
    await db_session.flush()

    response = await client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={"slot_id": str(overlap_slot.id)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_create_appointment_limit_exceeded(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_user,
    test_doctor: Doctor,
    db_session,
) -> None:
    """Patient cannot exceed active appointments limit.

    Default limit is 5 (from .env). Create 5 active appointments,
    then try a 6th.
    """

    base = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(days=10)
    for i in range(5):
        start = base + timedelta(hours=i + 1)
        end = start + timedelta(minutes=30)
        slot = ScheduleSlot(
            doctor_id=test_doctor.id,
            start_time=start,
            end_time=end,
            is_booked=True,
        )
        db_session.add(slot)
        await db_session.flush()

        appointment = Appointment(
            patient_id=test_user.id,
            doctor_id=test_doctor.id,
            slot_id=slot.id,
            status=AppointmentStatus.PENDING,
        )
        db_session.add(appointment)
        await db_session.flush()

    # Try the 6th
    start6 = base + timedelta(hours=10)
    end6 = start6 + timedelta(minutes=30)
    slot6 = ScheduleSlot(
        doctor_id=test_doctor.id,
        start_time=start6,
        end_time=end6,
        is_booked=False,
    )
    db_session.add(slot6)
    await db_session.flush()

    response = await client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={"slot_id": str(slot6.id)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_create_appointment_unauthenticated(
    client: AsyncClient, future_slot: ScheduleSlot
) -> None:
    """Unauthenticated booking returns 401."""
    response = await client.post(
        "/api/v1/appointments",
        json={"slot_id": str(future_slot.id)},
    )
    assert response.status_code == 401
