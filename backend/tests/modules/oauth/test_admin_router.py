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


async def test_connect_callback_answers_bad_state_with_400_not_401(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_owner(user_repository, uow, config, "oauthcb1")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.post(
        "/api/v1/auth/oauth/github/connect/callback",
        json={"code": "code", "state": "never-issued"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "OAUTH_STATE_INVALID"


async def test_connect_authorize_is_a_post(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    # it stores a fresh OAuth state, so it doesn't answer a GET
    owner = await _create_owner(user_repository, uow, config, "oauthauth1")
    headers = {
        "Authorization": f"Bearer {await _issue_token(owner.id, session_repository, config)}"
    }
    url = "/api/v1/auth/oauth/github/connect/authorize"

    assert (await client.get(url, headers=headers)).status_code == 405
    # reaches the usecase: GitHub isn't configured in the test settings
    assert (await client.post(url, headers=headers)).status_code == 400
