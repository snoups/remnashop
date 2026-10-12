from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1, CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.core.di.providers import get_core_providers
from app.core.security.session_token import derive_csrf_token
from app.modules.providers import get_module_providers

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
        *get_module_providers(),
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
    assert response.json()["code"] == "CSRF_FAILED"


async def test_refresh_rejects_a_forged_cookie_mirrored_into_the_header(
    auth_client: httpx.AsyncClient,
) -> None:
    # a plain double-submit check (cookie == header) would pass this; only an
    # HMAC of the real refresh token is accepted
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


async def test_refresh_rejection_carries_an_error_code(
    auth_client: httpx.AsyncClient, config: AppConfig
) -> None:
    unknown_token = "never-issued-refresh-token"
    csrf_token = derive_csrf_token(unknown_token, config.jwt_secret.get_secret_value())
    auth_client.cookies.set(REFRESH_COOKIE_NAME, unknown_token)
    auth_client.cookies.set(CSRF_COOKIE_NAME, csrf_token)

    response = await auth_client.post(
        f"{API_V1}/auth/refresh", headers={"X-Csrf-Token": csrf_token}
    )

    assert response.status_code == 401
    assert response.json()["code"]
