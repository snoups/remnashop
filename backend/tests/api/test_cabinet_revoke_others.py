import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.config.cabinet import CabinetConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.auth.usecases import RevokeOtherCabinetSessionsUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container

_URL = f"{API_V1}/auth/sessions/actions/revoke-others"


@pytest.fixture
async def container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    container = make_test_container(session, config)
    yield container
    await container.close()


@pytest.fixture
async def client(container: AsyncContainer, api_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    api_app.state.dishka_container = container
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def setup(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
):
    """A user with three CABINET sessions (the first is the caller's) and a DASHBOARD one."""
    async with uow:
        user = await user_repository.create(
            CreateUserDto(name="rev", telegram_id=911_001, role=Role.USER, language=Locale.EN)
        )
        await uow.commit()
    ids: dict[str, int] = {}
    for label, audience in (
        ("current", SessionAudience.CABINET),
        ("other1", SessionAudience.CABINET),
        ("other2", SessionAudience.CABINET),
        ("dashboard", SessionAudience.DASHBOARD),
    ):
        created = await session_repository.create(
            CreateSessionDto(
                user_id=user.id,
                refresh_token_hash=hash_refresh_token(f"rev-{label}"),
                ip_address="127.0.0.1",
                user_agent=None,
                expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
                audience=audience,
            )
        )
        ids[label] = created.id
    token = create_access_token(user.id, ids["current"], config.jwt_secret.get_secret_value())
    return user, ids, {"Authorization": f"Bearer {token}"}


async def test_revokes_other_cabinet_sessions_only(
    client: httpx.AsyncClient, setup, session_repository: SessionRepository
) -> None:
    user, ids, headers = setup

    response = await client.post(_URL, headers=headers)

    assert response.status_code == 204
    alive = {s.id for s in await session_repository.list_active_by_user(user.id)}
    assert alive == {ids["current"], ids["dashboard"]}


async def test_reachable_through_cabinet_proxy(
    config: AppConfig, container: AsyncContainer, setup
) -> None:
    _, _, headers = setup
    app = get_app(
        config.model_copy(update={"cabinet": CabinetConfig(proxy_secret=SecretStr("s3cret"))})
    )
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as proxied:
        response = await proxied.post(_URL, headers={**headers, "X-Cabinet-Proxy-Secret": "s3cret"})

    assert response.status_code == 204


async def test_is_rate_limited(client: httpx.AsyncClient, setup) -> None:
    _, _, headers = setup

    for _ in range(5):
        assert (await client.post(_URL, headers=headers)).status_code == 204
    blocked = await client.post(_URL, headers=headers)

    assert blocked.status_code == 429


async def test_dashboard_session_revokes_other_dashboard_sessions_only(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(login="rev-owner", name="rev", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    ids: dict[str, int] = {}
    for label, audience in (
        ("current", SessionAudience.DASHBOARD),
        ("other", SessionAudience.DASHBOARD),
        ("cabinet", SessionAudience.CABINET),
    ):
        created = await session_repository.create(
            CreateSessionDto(
                user_id=owner.id,
                refresh_token_hash=hash_refresh_token(f"rev-owner-{label}"),
                ip_address="127.0.0.1",
                user_agent=None,
                expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
                audience=audience,
            )
        )
        ids[label] = created.id
    token = create_access_token(owner.id, ids["current"], config.jwt_secret.get_secret_value())

    response = await client.post(_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    alive = {s.id for s in await session_repository.list_active_by_user(owner.id)}
    assert alive == {ids["current"], ids["cabinet"]}


async def test_the_bot_button_ends_every_cabinet_session(
    setup, session_repository: SessionRepository, uow: UnitOfWork
) -> None:
    user, ids, _ = setup
    use_case = RevokeOtherCabinetSessionsUseCase(session_repository, uow)

    await use_case(user, None)

    alive = {s.id for s in await session_repository.list_active_by_user(user.id)}
    assert alive == {ids["dashboard"]}
