"""Tests for authentication endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


# ============================================
# Registration
# ============================================


async def test_register_success(client: AsyncClient) -> None:
    """Register a new patient — returns 201 with role=patient."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "newpassword123",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["role"] == "patient"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data


async def test_register_duplicate_email(
    client: AsyncClient, test_user: User
) -> None:
    """Registering with an existing email returns 409."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "anypassword123",
            "full_name": "Another User",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_register_weak_password(client: AsyncClient) -> None:
    """Password shorter than 8 chars is rejected with 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak@example.com",
            "password": "short",
            "full_name": "Weak Password",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_register_invalid_email(client: AsyncClient) -> None:
    """Malformed email is rejected with 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "validpassword123",
            "full_name": "Bad Email",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ============================================
# Login
# ============================================


async def test_login_success(client: AsyncClient, test_user: User) -> None:
    """Valid credentials return a token pair."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(
    client: AsyncClient, test_user: User
) -> None:
    """Wrong password returns 401 with a generic message."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_login_unknown_email(client: AsyncClient) -> None:
    """Unknown email returns 401 (same as wrong password)."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "somepassword123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


# ============================================
# Refresh
# ============================================


async def test_refresh_success(client: AsyncClient, test_user: User) -> None:
    """Refresh with a valid token returns a new token pair."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Rotation: new refresh must differ from the old one
    assert data["refresh_token"] != refresh_token


async def test_refresh_reuse_revoked(
    client: AsyncClient, test_user: User
) -> None:
    """Using the same refresh twice fails the second time (rotation)."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    refresh_token = login.json()["refresh_token"]

    first = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert second.status_code == 401


async def test_refresh_with_access_token_fails(
    client: AsyncClient, test_user: User
) -> None:
    """Using an access token in place of a refresh token is rejected."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    access_token = login.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401


# ============================================
# Logout
# ============================================


async def test_logout_revokes_refresh(
    client: AsyncClient, test_user: User
) -> None:
    """After logout, the refresh token can no longer be used."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    refresh_token = login.json()["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout.status_code == 204

    refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh.status_code == 401
