"""Tests for doctor endpoints."""

from httpx import AsyncClient

from app.models.specialization import Specialization
from app.models.user import User

# ============================================
# Read (public)
# ============================================


async def test_list_doctors_empty(client: AsyncClient) -> None:
    """Empty catalog returns an empty page."""
    response = await client.get("/api/v1/doctors")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["size"] == 20


async def test_list_doctors_after_create(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization: Specialization,
) -> None:
    """Created doctor appears in the public list."""
    await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "doctor1@test.com",
            "password": "docpassword123",
            "full_name": "Иванов Иван",
            "specialization_id": str(test_specialization.id),
            "experience_years": 10,
            "avatar_url": "https://example.com/avatar.jpg",
        },
    )

    response = await client.get("/api/v1/doctors")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["full_name"] == "Иванов Иван"
    assert item["avatar_url"] == "https://example.com/avatar.jpg"
    assert item["specialization"]["name"] == "Терапевт"


async def test_get_doctor_detail(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization: Specialization,
) -> None:
    """Public GET /doctors/{id} returns full details."""
    created = await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "doctor2@test.com",
            "password": "docpassword123",
            "full_name": "Петров Пётр",
            "specialization_id": str(test_specialization.id),
            "bio": "Опытный терапевт",
            "experience_years": 15,
        },
    )
    doctor_id = created.json()["id"]

    response = await client.get(f"/api/v1/doctors/{doctor_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Петров Пётр"
    assert data["email"] == "doctor2@test.com"
    assert data["bio"] == "Опытный терапевт"
    assert data["experience_years"] == 15
    assert data["specialization"]["name"] == "Терапевт"


async def test_get_doctor_not_found(client: AsyncClient) -> None:
    """Unknown doctor id returns 404."""
    response = await client.get("/api/v1/doctors/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_list_doctors_filter_by_specialization(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization: Specialization,
) -> None:
    """Filter by specialization returns only matching doctors."""
    # Create second specialization
    other = await client.post(
        "/api/v1/specializations",
        headers=admin_headers,
        json={"name": "Кардиолог"},
    )
    other_id = other.json()["id"]

    # Create one doctor with each specialization
    await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "therapist@test.com",
            "password": "docpassword123",
            "full_name": "Терапевт",
            "specialization_id": str(test_specialization.id),
        },
    )
    await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "cardiologist@test.com",
            "password": "docpassword123",
            "full_name": "Кардиолог",
            "specialization_id": other_id,
        },
    )

    response = await client.get(
        "/api/v1/doctors",
        params={"specialization_id": str(test_specialization.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["full_name"] == "Терапевт"


# ============================================
# Write (admin only)
# ============================================


async def test_create_doctor_as_admin(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization: Specialization,
) -> None:
    """Admin creates a doctor with user account and profile."""
    response = await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "newdoc@test.com",
            "password": "newdocpassword123",
            "full_name": "Новый Доктор",
            "specialization_id": str(test_specialization.id),
            "bio": "Молодой специалист",
            "experience_years": 3,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newdoc@test.com"
    assert data["full_name"] == "Новый Доктор"
    assert data["bio"] == "Молодой специалист"
    assert "password" not in data
    assert "password_hash" not in data


async def test_create_doctor_as_patient_forbidden(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_specialization: Specialization,
) -> None:
    """Patient cannot create a doctor."""
    response = await client.post(
        "/api/v1/doctors",
        headers=auth_headers,
        json={
            "email": "hacker@test.com",
            "password": "hackerpass123",
            "full_name": "Хакер",
            "specialization_id": str(test_specialization.id),
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_create_doctor_unauthenticated(
    client: AsyncClient, test_specialization: Specialization
) -> None:
    """Unauthenticated user cannot create a doctor."""
    response = await client.post(
        "/api/v1/doctors",
        json={
            "email": "anon@test.com",
            "password": "anonpassword123",
            "full_name": "Аноним",
            "specialization_id": str(test_specialization.id),
        },
    )
    assert response.status_code == 401


async def test_create_doctor_invalid_specialization(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Creating a doctor with a non-existent specialization returns 404."""
    response = await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "orphan@test.com",
            "password": "orphanpass123",
            "full_name": "Без Специализации",
            "specialization_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_create_doctor_duplicate_email(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization: Specialization,
    test_user: User,
) -> None:
    """Creating a doctor with an existing user email returns 409."""
    response = await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "test@example.com",  # already exists as patient
            "password": "docpassword123",
            "full_name": "Дубликат",
            "specialization_id": str(test_specialization.id),
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_update_doctor(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization: Specialization,
) -> None:
    """Admin can update a doctor's profile."""
    created = await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "toupdate@test.com",
            "password": "toupdatepass123",
            "full_name": "До Обновления",
            "specialization_id": str(test_specialization.id),
            "experience_years": 5,
        },
    )
    doctor_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/doctors/{doctor_id}",
        headers=admin_headers,
        json={"bio": "Обновлённая биография", "experience_years": 7},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["bio"] == "Обновлённая биография"
    assert data["experience_years"] == 7
    assert data["full_name"] == "До Обновления"  # unchanged


async def test_delete_doctor(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization: Specialization,
) -> None:
    """Admin can delete a doctor (and linked user)."""
    created = await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "todelete@test.com",
            "password": "todeletepass123",
            "full_name": "На Удаление",
            "specialization_id": str(test_specialization.id),
        },
    )
    doctor_id = created.json()["id"]

    response = await client.delete(
        f"/api/v1/doctors/{doctor_id}",
        headers=admin_headers,
    )
    assert response.status_code == 204

    # Confirm it's gone
    response = await client.get(f"/api/v1/doctors/{doctor_id}")
    assert response.status_code == 404


# ============================================
# Caching
# ============================================


async def test_doctors_list_is_cached(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization: Specialization,
    fake_redis,
) -> None:
    """Doctor list is cached in Redis after first request."""
    # Create a doctor
    await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "cached@test.com",
            "password": "cachedpass123",
            "full_name": "Кешированный",
            "specialization_id": str(test_specialization.id),
        },
    )

    # No cache key yet for the default list
    keys_before = await fake_redis.keys("doctors:list:*")
    assert keys_before == []

    # First GET populates the cache
    response = await client.get("/api/v1/doctors")
    assert response.status_code == 200

    keys_after = await fake_redis.keys("doctors:list:*")
    assert len(keys_after) == 1

    # Second GET hits the cache (data unchanged even if we bypass DB)
    response2 = await client.get("/api/v1/doctors")
    assert response2.status_code == 200
    assert response2.json() == response.json()
