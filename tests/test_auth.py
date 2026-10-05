import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "AdminPassword123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "WrongPassword!"},
    )
    assert resp.status_code == 401
    err = resp.json()
    assert err["error"]["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_protected_route_unauthorized(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_success(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    user = resp.json()
    assert user["email"] == "admin@test.com"
    assert user["is_superuser"] is True


@pytest.mark.asyncio
async def test_api_key_creation_and_auth(client: AsyncClient, auth_headers: dict):
    # 1. Create API Key
    resp = await client.post(
        "/api/v1/auth/api-keys",
        headers=auth_headers,
        json={"name": "Dashboard Automation Key", "expires_days": 30},
    )
    assert resp.status_code == 201
    key_data = resp.json()
    assert "api_key" in key_data
    raw_key = key_data["api_key"]
    assert raw_key.startswith("lgk_live_")

    # 2. Use API Key to access protected route
    key_headers = {"Authorization": f"Bearer {raw_key}"}
    me_resp = await client.get("/api/v1/auth/me", headers=key_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@test.com"
