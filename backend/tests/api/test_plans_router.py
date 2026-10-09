import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.providers import get_module_providers
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_module_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _token_for(
    role: Role,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> str:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=f"planstest{role.value}",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=f"planstest{role.value}",
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{role.value}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    return create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())


async def test_list_plans_requires_admin_role(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.USER, user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/plans", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


async def test_list_plans_rejects_unauthenticated_request(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/plans")

    assert response.status_code == 401


async def test_owner_can_create_and_list_plan(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        f"{API_V1}/plans",
        headers=headers,
        json={
            "public_code": "basic",
            "name": "Basic",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
        },
    )
    assert create_response.status_code == 201

    list_response = await client.get(f"{API_V1}/plans", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1


async def test_catalog_excludes_inactive_plan_for_regular_user(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner_token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    await client.post(
        f"{API_V1}/plans",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "public_code": "basic",
            "name": "Basic",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
        },
    )

    user_token = await _token_for(Role.USER, user_repository, session_repository, uow, config)
    catalog_response = await client.get(
        f"{API_V1}/plans/catalog", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert catalog_response.status_code == 200
    assert catalog_response.json()["items"] == []


async def test_catalog_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/plans/catalog")

    assert response.status_code == 401


async def test_catalog_excludes_pii_and_infra_fields_for_active_plan(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner_token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    create_response = await client.post(
        f"{API_V1}/plans",
        headers=owner_headers,
        json={
            "public_code": "basic",
            "name": "Basic",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
        },
    )
    plan_id = create_response.json()["id"]
    await client.put(
        f"{API_V1}/plans/{plan_id}/durations",
        headers=owner_headers,
        json={"durations": [{"days": 30, "order_index": 0, "base_price": "9.99"}]},
    )
    await client.put(
        f"{API_V1}/plans/{plan_id}/squads",
        headers=owner_headers,
        json={"internal_squads": ["11111111-1111-1111-1111-111111111111"], "external_squad": None},
    )
    await client.patch(
        f"{API_V1}/plans/{plan_id}",
        headers=owner_headers,
        json={"is_active": True},
    )

    user_token = await _token_for(Role.USER, user_repository, session_repository, uow, config)
    catalog_response = await client.get(
        f"{API_V1}/plans/catalog", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert catalog_response.status_code == 200
    plan = catalog_response.json()["items"][0]
    assert "public_code" not in plan
    assert "allowed_emails" not in plan
    assert "allowed_telegram_ids" not in plan
    assert "internal_squads" not in plan
    assert "external_squad" not in plan
    assert "availability" not in plan
    assert "is_active" not in plan


async def test_catalog_refuses_an_api_token(
    client: httpx.AsyncClient, session: AsyncSession, uow: UnitOfWork
) -> None:
    # the catalog is filtered by the caller's own purchase history and referrer,
    # which a staff token doesn't have
    secret = "test-api-token-secret"
    async with uow:
        await ApiTokenRepository(session).create(
            CreateApiTokenDto(
                name="script",
                token_hash=hash_refresh_token(secret),
                scopes=[Permission.PLANS_VIEW.value],
                created_by_user_id=None,
                expires_at=None,
            )
        )

    response = await client.get(
        f"{API_V1}/plans/catalog", headers={"Authorization": f"Bearer {secret}"}
    )

    assert response.status_code == 403


async def test_plan_switches_default_on_and_can_be_turned_off(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        f"{API_V1}/plans",
        headers=headers,
        json={
            "public_code": "switches",
            "name": "Switches",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
        },
    )
    assert created.json()["allow_bonus_days"] is True
    assert created.json()["allow_promocodes"] is True

    patched = await client.patch(
        f"{API_V1}/plans/{created.json()['id']}",
        headers=headers,
        json={"allow_bonus_days": False, "allow_promocodes": False},
    )

    assert patched.status_code == 200
    assert patched.json()["allow_bonus_days"] is False
    assert patched.json()["allow_promocodes"] is False
