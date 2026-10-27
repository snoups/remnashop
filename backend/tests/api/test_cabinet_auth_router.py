import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import API_V1, DEFAULT_ALLOWED_EMAIL_DOMAINS
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container


@pytest.fixture
async def client(
    session: AsyncSession, config: AppConfig, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    container: AsyncContainer = make_test_container(session, config)
    app = api_app
    app.state.dishka_container = container
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
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    patched = await client.patch(
        f"{API_V1}/settings/cabinet-auth",
        json={"telegram_enabled": True, "telegram_oauth_enabled": True},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["telegram_oauth_enabled"] is True

    methods = await client.get(f"{API_V1}/auth/methods")
    assert methods.status_code == 200
    assert methods.json() == {
        "telegram_webapp": False,
        "telegram_deeplink": False,
        "email": False,
        "oauth": [],
        "allowed_email_domains": list(DEFAULT_ALLOWED_EMAIL_DOMAINS),
        "captcha": None,
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
    methods = await client.get(f"{API_V1}/auth/methods")
    assert methods.json()["oauth"] == ["telegram", "google"]

    # last: the rollback takes the uncommitted test session with it
    rejected = await client.patch(
        f"{API_V1}/settings/cabinet-auth", json={"email_enabled": True}, headers=headers
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "EMAIL_NOT_CONFIGURED"


async def test_captcha_secret_is_write_only(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    saved = await client.patch(
        f"{API_V1}/settings/cabinet-auth",
        json={"captcha_enabled": True, "captcha_site_key": "site", "captcha_secret_key": "s3cr3t"},
        headers=headers,
    )

    assert saved.status_code == 200
    assert saved.json()["is_captcha_configured"] is True
    assert "s3cr3t" not in saved.text


async def test_captcha_cannot_be_switched_on_without_keys(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    rejected = await client.patch(
        f"{API_V1}/settings/cabinet-auth",
        json={"captcha_enabled": True, "captcha_site_key": "site"},
        headers=headers,
    )

    assert rejected.status_code == 400
    assert rejected.json()["code"] == "CAPTCHA_NOT_CONFIGURED"
