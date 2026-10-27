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
from app.modules.settings.dto import UpdateOAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
async def client(
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
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


async def _create_owner(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig, login: str
) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=login,
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    return user


async def test_list_passkeys_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/passkeys")
    assert response.status_code == 401


async def test_list_passkeys_returns_empty_for_new_owner(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_owner(user_repository, uow, config, "pkowner1")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.get(
        "/api/v1/auth/passkeys", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_get_registration_options_rejects_when_disabled(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_owner(user_repository, uow, config, "pkowner2")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.get(
        "/api/v1/auth/passkeys/register/options", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400


async def test_get_registration_options_returns_options_when_enabled(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_owner(user_repository, uow, config, "pkowner3")
    token = await _issue_token(owner.id, session_repository, config)
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            passkey_enabled=True, passkey_rp_id="testserver", passkey_origin="https://testserver"
        )
    )

    response = await client.get(
        "/api/v1/auth/passkeys/register/options", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["rp"]["id"] == "testserver"


async def test_rename_passkey_rejects_unknown_id(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_owner(user_repository, uow, config, "pkowner4")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.patch(
        "/api/v1/auth/passkeys/999999",
        json={"name": "New name"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


async def test_delete_passkey_rejects_unknown_id(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_owner(user_repository, uow, config, "pkowner5")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.delete(
        "/api/v1/auth/passkeys/999999", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
