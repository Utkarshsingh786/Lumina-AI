"""Integration tests for auth endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, sample_user_data: dict):
    response = await client.post("/api/v1/auth/register", json=sample_user_data)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, sample_user_data: dict):
    await client.post("/api/v1/auth/register", json=sample_user_data)
    # Second registration with same email
    response = await client.post("/api/v1/auth/register", json=sample_user_data)
    assert response.status_code == 409
    assert response.json()["error_code"] == "EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, sample_user_data: dict):
    await client.post("/api/v1/auth/register", json=sample_user_data)
    response = await client.post("/api/v1/auth/login", json={
        "email": sample_user_data["email"],
        "password": sample_user_data["password"],
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, sample_user_data: dict):
    await client.post("/api/v1/auth/register", json=sample_user_data)
    response = await client.post("/api/v1/auth/login", json={
        "email": sample_user_data["email"],
        "password": "WrongPassword99",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, sample_user_data: dict):
    reg = await client.post("/api/v1/auth/register", json=sample_user_data)
    token = reg.json()["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == sample_user_data["email"]


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
