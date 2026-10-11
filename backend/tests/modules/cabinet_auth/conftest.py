from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.email import SendEmailDispatch
from app.modules.providers import get_module_providers
from tests.fakes.dispatch import RecordingDispatch


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


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
    container = make_async_container(
        *get_core_providers(),
        *get_module_providers(),
        _TestSessionProvider(session),
        _EmailDispatchProvider(email_dispatch),
        context={AppConfig: config},
    )
    yield container
    await container.close()


@pytest.fixture
async def sign_in(container: AsyncContainer) -> AsyncIterator[CabinetSignIn]:
    async with container() as request_container:
        yield await request_container.get(CabinetSignIn)


@pytest.fixture
async def client(config: AppConfig, container: AsyncContainer) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
