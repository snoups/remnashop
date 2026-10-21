import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

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
from tests.fakes.container import make_test_container


@pytest.fixture
async def client(session: AsyncSession, config: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    container: AsyncContainer = make_test_container(session, config)
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
                login="emailsettingsowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="emailsettingsowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-email-settings"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_email_settings_response_never_carries_the_password(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    before = await client.get(f"{API_V1}/settings/email", headers=headers)
    assert before.status_code == 200
    assert before.json()["is_password_set"] is False

    patched = await client.patch(
        f"{API_V1}/settings/email",
        json={"host": "smtp.example.com", "from_address": "a@example.com", "password": "secret-pw"},
        headers=headers,
    )
    assert patched.status_code == 200
    after = await client.get(f"{API_V1}/settings/email", headers=headers)

    for response in (patched, after):
        body = response.json()
        assert "password" not in body
        assert "secret-pw" not in response.text
        assert body["is_password_set"] is True
        assert body["is_configured"] is True
