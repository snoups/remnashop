import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
async def client(
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    api_app.state.dishka_container = test_container
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest.fixture
async def owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login="promotest",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="promotest",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-promo"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_a_null_lifts_a_promocode_limit_and_a_missing_field_keeps_it(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    created = await client.post(
        f"{API_V1}/promocodes",
        headers=owner_headers,
        json={
            "code": "LIFTME",
            "reward_type": "DURATION",
            "reward": 7,
            "expires_at": "2099-01-01T00:00:00Z",
            "max_activations": 5,
        },
    )
    assert created.status_code == 201

    response = await client.patch(
        f"{API_V1}/promocodes/{created.json()['id']}",
        headers=owner_headers,
        json={"expires_at": None},
    )

    assert response.status_code == 200
    assert (response.json()["expires_at"], response.json()["max_activations"]) == (None, 5)


async def test_an_unknown_plan_in_a_patch_is_a_bad_body_and_an_unknown_promocode_a_404(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    created = await client.post(
        f"{API_V1}/promocodes",
        headers=owner_headers,
        json={"code": "PLANLIMIT", "reward_type": "DURATION", "reward": 7},
    )

    bad_plan = await client.patch(
        f"{API_V1}/promocodes/{created.json()['id']}",
        headers=owner_headers,
        json={"allowed_plan_ids": [999_999]},
    )
    missing = await client.patch(
        f"{API_V1}/promocodes/999999", headers=owner_headers, json={"is_active": False}
    )

    assert (bad_plan.status_code, bad_plan.json()["code"]) == (400, "PLAN_NOT_FOUND")
    assert missing.status_code == 404
