from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.di.providers import get_core_providers
from app.modules.auth import get_auth_providers
from app.modules.settings import get_settings_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers

_BOOTSTRAP_PASSWORD = "Sup3rSecurePassword12345"


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


@pytest.fixture
async def auth_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_auth_providers(),
        *get_users_providers(),
        *get_settings_providers(),
        *get_translations_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def auth_client(
    config: AppConfig, auth_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(auth_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _bootstrap(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post(
        f"{API_V1}/auth/bootstrap",
        json={"login": "csrf-owner", "password": _BOOTSTRAP_PASSWORD},
    )


async def test_refresh_succeeds_with_the_issued_csrf_token(auth_client: httpx.AsyncClient) -> None:
    bootstrap_response = await _bootstrap(auth_client)
    assert bootstrap_response.status_code == 201
    csrf_token = auth_client.cookies.get("csrf_token")
    assert csrf_token

    response = await auth_client.post(
        f"{API_V1}/auth/refresh", headers={"X-Csrf-Token": csrf_token}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rejects_a_missing_csrf_header(auth_client: httpx.AsyncClient) -> None:
    assert (await _bootstrap(auth_client)).status_code == 201

    response = await auth_client.post(f"{API_V1}/auth/refresh")

    assert response.status_code == 403


async def test_refresh_rejects_a_forged_cookie_mirrored_into_the_header(
    auth_client: httpx.AsyncClient,
) -> None:
    # The core of the fix: a plain double-submit (cookie==header) would pass
    # this, since both are set to the same attacker-chosen value. Only a
    # correctly-signed value (HMAC of the real refresh token) is accepted.
    assert (await _bootstrap(auth_client)).status_code == 201
    auth_client.cookies.set("csrf_token", "attacker-controlled-value")

    response = await auth_client.post(
        f"{API_V1}/auth/refresh", headers={"X-Csrf-Token": "attacker-controlled-value"}
    )

    assert response.status_code == 403


async def test_logout_succeeds_with_the_issued_csrf_token(auth_client: httpx.AsyncClient) -> None:
    assert (await _bootstrap(auth_client)).status_code == 201
    csrf_token = auth_client.cookies.get("csrf_token")
    assert csrf_token

    response = await auth_client.post(f"{API_V1}/auth/logout", headers={"X-Csrf-Token": csrf_token})

    assert response.status_code == 204


async def test_logout_rejects_a_forged_cookie_mirrored_into_the_header(
    auth_client: httpx.AsyncClient,
) -> None:
    assert (await _bootstrap(auth_client)).status_code == 201
    auth_client.cookies.set("csrf_token", "attacker-controlled-value")

    response = await auth_client.post(
        f"{API_V1}/auth/logout", headers={"X-Csrf-Token": "attacker-controlled-value"}
    )

    assert response.status_code == 403
