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


async def test_list_sessions_returns_own_session(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "sessionowner")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.get(
        "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


async def test_revoke_session_rejects_unknown_id(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "sessionowner2")
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.delete(
        "/api/v1/auth/sessions/999999", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


async def test_revoke_user_session_rejects_higher_privileged_target(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    # USER_SESSIONS_REVOKE still can't touch an OWNER's session: the usecase's
    # role-hierarchy check
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "targetowner")
    owner_session_id = (
        await session_repository.create(
            CreateSessionDto(
                user_id=owner.id,
                refresh_token_hash=hash_refresh_token("owner-refresh-token"),
                ip_address="127.0.0.1",
                user_agent=None,
                expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
                audience=SessionAudience.DASHBOARD,
            )
        )
    ).id

    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="revokeadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="revokeadmin",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_grants=["USER_SESSIONS_REVOKE"],
            )
        )
        await uow.commit()
    admin_token = await _issue_token(admin.id, session_repository, config)

    response = await client.delete(
        f"/api/v1/users/{owner.id}/sessions/{owner_session_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
