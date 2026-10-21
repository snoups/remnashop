import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka

from app.api.app import get_app
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
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
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
        owner = await user_repository.create(
            CreateUserDto(
                login="loyaltyowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="loyaltyowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=owner.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-loyalty-owner"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(owner.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_put_loyalty_settings_round_trips(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.put(
        f"{API_V1}/loyalty/settings",
        json={
            "enabled": True,
            "window_months": None,
            "tiers": [{"threshold": "1000", "percent": 3}],
        },
        headers=owner_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["window_months"] is None
    assert body["tiers"] == [{"threshold": "1000.00", "percent": 3}]
    assert body["currency"]


async def test_put_loyalty_settings_rejects_decreasing_tiers(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.put(
        f"{API_V1}/loyalty/settings",
        json={
            "enabled": True,
            "window_months": 6,
            "tiers": [{"threshold": "1000", "percent": 5}, {"threshold": "500", "percent": 7}],
        },
        headers=owner_headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "LOYALTY_TIERS_INVALID"


async def test_user_loyalty_get_and_exclude(
    client: httpx.AsyncClient, owner_headers: dict[str, str], user_repository: UserRepository
) -> None:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=990_101))

    got = await client.get(f"{API_V1}/users/{user.id}/loyalty", headers=owner_headers)
    patched = await client.patch(
        f"{API_V1}/users/{user.id}/loyalty", json={"excluded": True}, headers=owner_headers
    )

    assert got.status_code == 200
    assert got.json()["discount"] == 0
    assert patched.status_code == 200
    assert patched.json()["excluded"] is True
