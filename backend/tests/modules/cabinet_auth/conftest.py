from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.email import SendEmailDispatch
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
