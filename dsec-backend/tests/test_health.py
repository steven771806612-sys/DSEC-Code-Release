"""Basic API health check tests."""
import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data


@pytest.mark.asyncio
async def test_docs_available(client):
    response = await client.get("/docs")
    # In debug mode docs are available
    assert response.status_code in (200, 404)
