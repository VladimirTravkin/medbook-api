"""Tests for the health endpoint."""

from httpx import AsyncClient


async def test_health_ok(client: AsyncClient) -> None:
    """Health endpoint should report ok when DB and Redis are reachable."""
    response = await client.get("/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["redis"] == "ok"
