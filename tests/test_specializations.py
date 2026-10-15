"""Tests for specialization endpoints."""

from httpx import AsyncClient

from app.models.user import User

# ============================================
# Read (public)
# ============================================


async def test_list_specializations_empty(client: AsyncClient) -> None:
    """Empty catalog returns an empty list."""
    response = await client.get("/api/v1/specializations")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_specializations(client: AsyncClient, test_specialization) -> None:
    """Catalog returns the created specialization."""
    response = await client.get("/api/v1/specializations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Терапевт"


async def test_get_specialization(client: AsyncClient, test_specialization) -> None:
    """Get a single specialization by id."""
    response = await client.get(f"/api/v1/specializations/{test_specialization.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Терапевт"


async def test_get_specialization_not_found(client: AsyncClient) -> None:
    """Unknown id returns 404."""
    response = await client.get("/api/v1/specializations/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ============================================
# Write (admin only)
# ============================================


async def test_create_specialization_as_admin(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Admin can create a specialization."""
    response = await client.post(
        "/api/v1/specializations",
        headers=admin_headers,
        json={"name": "Кардиолог", "description": "Сердечно-сосудистые заболевания"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Кардиолог"
    assert data["id"]


async def test_create_specialization_as_patient_forbidden(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Patient cannot create a specialization."""
    response = await client.post(
        "/api/v1/specializations",
        headers=auth_headers,
        json={"name": "Хирург"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_create_specialization_unauthenticated(client: AsyncClient) -> None:
    """Unauthenticated user cannot create a specialization."""
    response = await client.post(
        "/api/v1/specializations",
        json={"name": "Хирург"},
    )
    assert response.status_code == 401


async def test_create_specialization_duplicate(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization,
) -> None:
    """Creating a specialization with an existing name returns 409."""
    response = await client.post(
        "/api/v1/specializations",
        headers=admin_headers,
        json={"name": "Терапевт"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_update_specialization(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization,
) -> None:
    """Admin can update a specialization."""
    response = await client.patch(
        f"/api/v1/specializations/{test_specialization.id}",
        headers=admin_headers,
        json={"description": "Обновлённое описание"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Обновлённое описание"
    assert response.json()["name"] == "Терапевт"


async def test_delete_specialization(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization,
) -> None:
    """Admin can delete an unused specialization."""
    response = await client.delete(
        f"/api/v1/specializations/{test_specialization.id}",
        headers=admin_headers,
    )
    assert response.status_code == 204

    # Confirm it's gone
    response = await client.get(f"/api/v1/specializations/{test_specialization.id}")
    assert response.status_code == 404


async def test_delete_specialization_in_use(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_specialization,
    test_admin: User,
) -> None:
    """Cannot delete a specialization that has doctors attached."""
    # Create a doctor with this specialization
    create = await client.post(
        "/api/v1/doctors",
        headers=admin_headers,
        json={
            "email": "doc1@test.com",
            "password": "docpassword123",
            "full_name": "Доктор Тестов",
            "specialization_id": str(test_specialization.id),
            "experience_years": 5,
        },
    )
    assert create.status_code == 201, create.text

    # Try to delete the specialization
    response = await client.delete(
        f"/api/v1/specializations/{test_specialization.id}",
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
