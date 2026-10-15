"""Tests for schedule slot endpoints."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.models.doctor import Doctor
from app.models.schedule_slot import ScheduleSlot

# ============================================
# List (public)
# ============================================


async def test_list_slots_empty(client: AsyncClient, test_doctor: Doctor) -> None:
    """Doctor with no slots returns an empty page."""
    response = await client.get(f"/api/v1/doctors/{test_doctor.id}/slots")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_slots_with_slot(
    client: AsyncClient,
    test_doctor: Doctor,
    future_slot: ScheduleSlot,
) -> None:
    """Slot appears in the public list."""
    response = await client.get(f"/api/v1/doctors/{test_doctor.id}/slots")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(future_slot.id)
    assert data["items"][0]["is_booked"] is False


# ============================================
# Create (doctor/admin)
# ============================================


async def test_create_slot_as_doctor(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    test_doctor: Doctor,
) -> None:
    """Doctor can create a slot for themselves."""
    start = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(days=5)
    end = start + timedelta(minutes=30)

    response = await client.post(
        f"/api/v1/doctors/{test_doctor.id}/slots",
        headers=doctor_headers,
        json={
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["doctor_id"] == str(test_doctor.id)
    assert data["is_booked"] is False


async def test_create_slot_as_doctor_for_other_forbidden(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    admin_headers: dict[str, str],
    test_specialization,
) -> None:
    """Doctor cannot create a slot for another doctor."""
    # Create another doctor via admin
    other = await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "otherdoc@test.com",
            "password": "otherdocpass123",
            "full_name": "Другой Доктор",
            "specialization_id": str(test_specialization.id),
        },
    )
    other_doctor_id = other.json()["id"]

    start = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(days=5)
    end = start + timedelta(minutes=30)

    response = await client.post(
        f"/api/v1/doctors/{other_doctor_id}/slots",
        headers=doctor_headers,
        json={
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_create_slot_patient_forbidden(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_doctor: Doctor,
) -> None:
    """Patient cannot create slots."""
    start = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(days=5)
    end = start + timedelta(minutes=30)

    response = await client.post(
        f"/api/v1/doctors/{test_doctor.id}/slots",
        headers=auth_headers,
        json={
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert response.status_code == 403


async def test_create_slot_overlap_conflict(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    test_doctor: Doctor,
    future_slot: ScheduleSlot,
) -> None:
    """Slot overlapping an existing one returns 409."""
    # Overlapping range: same start as future_slot
    response = await client.post(
        f"/api/v1/doctors/{test_doctor.id}/slots",
        headers=doctor_headers,
        json={
            "start_time": future_slot.start_time.isoformat(),
            "end_time": future_slot.end_time.isoformat(),
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_create_slot_in_past(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    test_doctor: Doctor,
) -> None:
    """Slot in the past returns 400."""
    start = datetime.now(UTC) - timedelta(days=1)
    end = start + timedelta(minutes=30)

    response = await client.post(
        f"/api/v1/doctors/{test_doctor.id}/slots",
        headers=doctor_headers,
        json={
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert response.status_code == 400


# ============================================
# Generate (doctor/admin)
# ============================================


async def test_generate_slots(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    test_doctor: Doctor,
) -> None:
    """Bulk generation creates slots for a weekday range."""
    # Pick a Monday..Friday window starting next week
    today = datetime.now(UTC).date()
    days_ahead = 7 - today.weekday()  # to next Monday
    next_monday = today + timedelta(days=days_ahead)
    next_friday = next_monday + timedelta(days=4)

    response = await client.post(
        f"/api/v1/doctors/{test_doctor.id}/slots/generate",
        headers=doctor_headers,
        json={
            "date_from": f"{next_monday.isoformat()}T00:00:00+00:00",
            "date_to": f"{next_friday.isoformat()}T23:59:59+00:00",
            "work_day_start": "09:00:00",
            "work_day_end": "12:00:00",
            "slot_duration_minutes": 30,
            "weekdays": [1, 2, 3, 4, 5],
        },
    )
    assert response.status_code == 200
    data = response.json()
    # 5 weekdays * 6 slots per day (9:00 to 12:00, 30 min) = 30
    assert data["created"] == 30
    assert data["skipped"] == 0


async def test_generate_slots_skips_existing(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    test_doctor: Doctor,
) -> None:
    """Second generation run skips already existing slots."""
    today = datetime.now(UTC).date()
    days_ahead = 7 - today.weekday()
    next_monday = today + timedelta(days=days_ahead)
    next_tuesday = next_monday + timedelta(days=1)

    payload = {
        "date_from": f"{next_monday.isoformat()}T00:00:00+00:00",
        "date_to": f"{next_tuesday.isoformat()}T23:59:59+00:00",
        "work_day_start": "09:00:00",
        "work_day_end": "10:00:00",
        "slot_duration_minutes": 30,
        "weekdays": [1, 2],
    }

    first = await client.post(
        f"/api/v1/doctors/{test_doctor.id}/slots/generate",
        headers=doctor_headers,
        json=payload,
    )
    assert first.status_code == 200
    assert first.json()["created"] == 4  # 2 days * 2 slots

    second = await client.post(
        f"/api/v1/doctors/{test_doctor.id}/slots/generate",
        headers=doctor_headers,
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == 4


# ============================================
# Delete (doctor/admin)
# ============================================


async def test_delete_slot(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    test_doctor: Doctor,
    future_slot: ScheduleSlot,
) -> None:
    """Doctor can delete their own free slot."""
    response = await client.delete(
        f"/api/v1/slots/{future_slot.id}",
        headers=doctor_headers,
    )
    assert response.status_code == 204

    # Confirm gone
    response = await client.get(f"/api/v1/doctors/{test_doctor.id}/slots")
    assert response.json()["total"] == 0


async def test_delete_booked_slot_forbidden(
    client: AsyncClient,
    doctor_headers: dict[str, str],
    booked_slot: ScheduleSlot,
) -> None:
    """Booked slot cannot be deleted."""
    response = await client.delete(
        f"/api/v1/slots/{booked_slot.id}",
        headers=doctor_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
