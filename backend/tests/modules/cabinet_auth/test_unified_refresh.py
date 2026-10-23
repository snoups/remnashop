from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from pydantic import SecretStr

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.config.cabinet import CabinetConfig
from app.core.constants import API_V1
from app.core.enums import SessionAudience
from app.modules.auth import SESSION_COOKIES, IssuedSession, SessionIssuer
from app.modules.cabinet_auth.dto import InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.sign_in import CabinetSignIn

_IP = "203.0.113.1"
_REFRESH = f"{API_V1}/auth/refresh"


async def _sessions(
    sign_in: CabinetSignIn, container: AsyncContainer
) -> tuple[IssuedSession, IssuedSession]:
    user, cabinet = await sign_in.telegram(
        TelegramProfileDto(telegram_id=9411, name="Ann", username=None, language="en"),
        InviteCodesDto(),
        _IP,
        None,
    )
    async with container() as request_container:
        issuer = await request_container.get(SessionIssuer)
        dashboard = await issuer.issue(user.id, _IP, None, audience=SessionAudience.DASHBOARD)
    return cabinet, dashboard


def _use(
    client: httpx.AsyncClient, issued: IssuedSession, audience: SessionAudience
) -> dict[str, str]:
    cookies = SESSION_COOKIES[audience]
    client.cookies.set(cookies.refresh, issued.refresh_token)
    client.cookies.set(cookies.csrf, issued.csrf_token)
    return {"X-Csrf-Token": issued.csrf_token}


async def test_each_audience_refreshes_only_its_own_session(
    client: httpx.AsyncClient, sign_in: CabinetSignIn, container: AsyncContainer
) -> None:
    cabinet, dashboard = await _sessions(sign_in, container)

    headers = _use(client, cabinet, SessionAudience.CABINET)
    response = await client.post(_REFRESH, headers=headers)
    assert response.status_code == 200
    assert response.json()["expires_in"] > 0
    assert response.cookies.get("cabinet_refresh_token")
    assert response.cookies.get("refresh_token") is None

    client.cookies.clear()
    headers = _use(client, dashboard, SessionAudience.DASHBOARD)
    response = await client.post(_REFRESH, headers=headers)
    assert response.status_code == 200
    assert response.cookies.get("refresh_token")
    assert response.cookies.get("cabinet_refresh_token") is None


async def test_a_dashboard_token_in_the_cabinet_cookie_is_refused(
    client: httpx.AsyncClient, sign_in: CabinetSignIn, container: AsyncContainer
) -> None:
    _, dashboard = await _sessions(sign_in, container)
    client.cookies.set("cabinet_refresh_token", dashboard.refresh_token)
    client.cookies.set("cabinet_csrf_token", dashboard.csrf_token)

    response = await client.post(_REFRESH, headers={"X-Csrf-Token": dashboard.csrf_token})

    assert response.status_code == 401


async def test_a_tossed_cabinet_cookie_does_not_break_the_dashboard_refresh(
    client: httpx.AsyncClient, sign_in: CabinetSignIn, container: AsyncContainer
) -> None:
    cabinet, dashboard = await _sessions(sign_in, container)
    _use(client, cabinet, SessionAudience.CABINET)
    headers = _use(client, dashboard, SessionAudience.DASHBOARD)

    # not through the cabinet's proxy: the dashboard's own cookie is the one used
    response = await client.post(_REFRESH, headers=headers)

    assert response.status_code == 200


@pytest.fixture
async def proxied_client(
    config: AppConfig, container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(
        config.model_copy(update={"cabinet": CabinetConfig(proxy_secret=SecretStr("s3cret"))})
    )
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_a_dashboard_refresh_is_refused_through_the_proxy(
    proxied_client: httpx.AsyncClient, sign_in: CabinetSignIn, container: AsyncContainer
) -> None:
    _, dashboard = await _sessions(sign_in, container)
    headers = _use(proxied_client, dashboard, SessionAudience.DASHBOARD)

    response = await proxied_client.post(
        _REFRESH, headers={**headers, "X-Cabinet-Proxy-Secret": "s3cret"}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PROXY_DASHBOARD_FORBIDDEN"


async def test_logout_revokes_the_presented_audience(
    client: httpx.AsyncClient, sign_in: CabinetSignIn, container: AsyncContainer
) -> None:
    cabinet, _ = await _sessions(sign_in, container)
    headers = _use(client, cabinet, SessionAudience.CABINET)

    assert (await client.post(f"{API_V1}/auth/logout", headers=headers)).status_code == 204

    headers = _use(client, cabinet, SessionAudience.CABINET)
    assert (await client.post(_REFRESH, headers=headers)).status_code == 401


async def test_cabinet_methods_live_under_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"{API_V1}/auth/methods")).status_code == 200
    assert (await client.get(f"{API_V1}/cabinet/auth/methods")).status_code == 404
