import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
async def client(
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    # same fixture as tests/modules/users/test_admin_router.py
    app = api_app
    app.state.dishka_container = test_container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _issue_token(
    user_id: int, session_repository: SessionRepository, config: AppConfig
) -> str:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token("test-refresh-token"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    return create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())


async def _create_user(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig, role: Role, login: str
) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=login,
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    return user


async def test_create_and_list_api_tokens(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "tokenowner")
    token = await _issue_token(owner.id, session_repository, config)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/api-tokens",
        json={"name": "ci-bot", "scopes": ["EVENT_LOG_VIEW"], "expires_in_days": 30},
        headers=headers,
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["token"]["name"] == "ci-bot"
    assert body["token"]["scopes"] == ["EVENT_LOG_VIEW"]
    assert body["secret"]

    list_response = await client.get("/api/v1/api-tokens", headers=headers)
    assert list_response.status_code == 200
    names = [item["name"] for item in list_response.json()["items"]]
    assert "ci-bot" in names


async def test_create_api_token_rejects_non_grantable_permission(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "tokenowner2")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.post(
        "/api/v1/api-tokens",
        json={"name": "bad-scope", "scopes": ["OWN_ACCOUNT_MANAGE"], "expires_in_days": 30},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


async def test_revoke_api_token_rejects_unknown_id(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "tokenowner3")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.delete(
        "/api/v1/api-tokens/999999", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


async def test_api_tokens_router_rejects_admin_without_grant(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    # ADMIN lacks API_TOKENS_MANAGE: the usecase gate, not require_admin
    admin = await _create_user(user_repository, uow, config, Role.ADMIN, "plainadmin2")
    token = await _issue_token(admin.id, session_repository, config)

    response = await client.get("/api/v1/api-tokens", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
