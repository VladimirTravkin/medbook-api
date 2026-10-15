"""Tests for user profile endpoints."""

from httpx import AsyncClient

from app.models.user import User


# ============================================
# GET /users/me
# ============================================


async def test_get_me_authenticated(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Authenticated user can fetch their own profile."""
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test Patient"
    assert data["role"] == "patient"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data


async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    """Request without a token returns 401."""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


async def test_get_me_invalid_token(client: AsyncClient) -> None:
    """Malformed token returns 401."""
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401


async def test_get_me_refresh_token_rejected(
    client: AsyncClient, test_user: User
) -> None:
    """Refresh token must not be accepted as an access token."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 401


# ============================================
# PATCH /users/me
# ============================================


async def test_update_me_full_name(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Authenticated user can update their own full_name."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "Updated Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["email"] == "test@example.com"  # unchanged


async def test_update_me_empty_body(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PATCH with an empty body does not change anything and returns 200."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Test Patient"


async def test_update_me_unauthenticated(client: AsyncClient) -> None:
    """PATCH without a token returns 401."""
    response = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "Hacker"},
    )
    assert response.status_code == 401
