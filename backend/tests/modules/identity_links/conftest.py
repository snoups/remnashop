from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, provide
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.enums import SessionAudience
from app.core.security import create_access_token, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.email import SendEmailDispatch
from app.modules.identity_links.linker import IdentityLinker
from tests.fakes.container import make_test_container
from tests.fakes.dispatch import RecordingDispatch


class _EmailDispatchProvider(Provider):
    scope = Scope.APP

    def __init__(self, dispatch: RecordingDispatch) -> None:
        super().__init__()
        self._dispatch = dispatch

    @provide(override=True)
    def get_dispatch(self) -> SendEmailDispatch:
        return self._dispatch


@pytest.fixture
def email_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
async def container(
    session: AsyncSession, config: AppConfig, email_dispatch: RecordingDispatch
) -> AsyncIterator[AsyncContainer]:
    container = make_test_container(session, config, _EmailDispatchProvider(email_dispatch))
    yield container
    await container.close()


@pytest.fixture
async def linker(container: AsyncContainer) -> AsyncIterator[IdentityLinker]:
    async with container() as request_container:
        yield await request_container.get(IdentityLinker)


@pytest.fixture
async def client(container: AsyncContainer, api_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    app = api_app
    app.state.dishka_container = container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def bearer(
    user_id: int,
    session_repository: SessionRepository,
    config: AppConfig,
    audience: SessionAudience = SessionAudience.CABINET,
) -> dict[str, str]:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(f"identity-links-{user_id}-{audience}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            audience=audience,
        )
    )
    token = create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}
