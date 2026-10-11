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
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
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
async def client(session: AsyncSession, config: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    container: AsyncContainer = make_async_container(
        *get_core_providers(),
        *get_module_providers(),
        _TestSessionProvider(session),
        context={AppConfig: config},
    )
    app = get_app(config)
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    await container.close()


async def _owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login="cabinetauthowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="cabinetauthowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-cabinet-auth"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_methods_is_public_and_lowercases_providers(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "web_cabinet_url", "https://cabinet.example.com")
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    patched = await client.patch(
        f"{API_V1}/settings/cabinet-auth", json={"telegram_enabled": True}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["telegram_enabled"] is True

    methods = await client.get(f"{API_V1}/cabinet/auth/methods")
    assert methods.status_code == 200
    assert methods.json() == {
        "telegram_webapp": False,
        "telegram_deeplink": False,
        "email": False,
        "oauth": [],
    }

    enabled = await client.patch(
        f"{API_V1}/settings/cabinet-auth", json={"google_enabled": True}, headers=headers
    )
    assert enabled.status_code == 200
    configured = await client.patch(
        f"{API_V1}/settings/oauth",
        json={
            "telegram_client_id": "t",
            "telegram_client_secret": "t",
            "google_client_id": "g",
            "google_client_secret": "g",
        },
        headers=headers,
    )
    assert configured.status_code == 200
    assert configured.json()["is_google_configured"] is True
    methods = await client.get(f"{API_V1}/cabinet/auth/methods")
    assert methods.json()["oauth"] == ["telegram", "google"]

    # last: the rollback takes the uncommitted test session with it
    rejected = await client.patch(
        f"{API_V1}/settings/cabinet-auth", json={"email_enabled": True}, headers=headers
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "EMAIL_NOT_CONFIGURED"
