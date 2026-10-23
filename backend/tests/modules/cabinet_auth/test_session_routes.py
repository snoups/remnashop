import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import httpx
from dishka import AsyncContainer

from app.core.config import AppConfig
from app.core.constants import (
    API_V1,
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    TTL_7D,
    TTL_15M,
    TTL_30D,
)
from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience
from app.core.security import derive_csrf_token, hash_refresh_token
from app.core.utils.time import datetime_now
from app.modules.auth import SESSION_COOKIES
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import IssuedSession, SessionIssuer
from app.modules.cabinet_auth.dto import InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.settings.dto import UpdateBotSettingsDto, UpdateCabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository

_IP = "203.0.113.1"
_CABINET_REFRESH = SESSION_COOKIES[SessionAudience.CABINET].refresh
_CABINET_CSRF = SESSION_COOKIES[SessionAudience.CABINET].csrf
_BOT_TOKEN = "123456:TEST-token"


async def _sign_in(sign_in: CabinetSignIn) -> tuple[UserDto, IssuedSession]:
    return await sign_in.telegram(
        TelegramProfileDto(telegram_id=9301, name="Ann", username="ann", language="en"),
        InviteCodesDto(),
        _IP,
        None,
    )


async def _dashboard_session(sign_in: CabinetSignIn, container: AsyncContainer) -> IssuedSession:
    user, _ = await _sign_in(sign_in)
    async with container() as request_container:
        issuer = await request_container.get(SessionIssuer)
        return await issuer.issue(user.id, _IP, None, audience=SessionAudience.DASHBOARD)


def _set_cookies(
    client: httpx.AsyncClient, issued: IssuedSession, refresh_cookie: str, csrf_cookie: str
) -> dict[str, str]:
    client.cookies.set(refresh_cookie, issued.refresh_token)
    client.cookies.set(csrf_cookie, issued.csrf_token)
    return {"X-Csrf-Token": issued.csrf_token}


async def test_cabinet_refresh_rotates_a_cabinet_session(
    client: httpx.AsyncClient, sign_in: CabinetSignIn
) -> None:
    _, issued = await _sign_in(sign_in)
    headers = _set_cookies(client, issued, _CABINET_REFRESH, _CABINET_CSRF)

    response = await client.post(f"{API_V1}/auth/refresh", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["expires_in"] == TTL_15M
    assert response.cookies.get(_CABINET_REFRESH) not in (None, issued.refresh_token)


async def test_cabinet_refresh_rejects_a_missing_csrf_header(
    client: httpx.AsyncClient, sign_in: CabinetSignIn
) -> None:
    _, issued = await _sign_in(sign_in)
    _set_cookies(client, issued, _CABINET_REFRESH, _CABINET_CSRF)

    response = await client.post(f"{API_V1}/auth/refresh")

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_FAILED"


async def test_cabinet_refresh_failure_clears_cookies(
    client: httpx.AsyncClient, config: AppConfig
) -> None:
    csrf = derive_csrf_token("unknown-refresh-token", config.jwt_secret.get_secret_value())
    client.cookies.set(_CABINET_REFRESH, "unknown-refresh-token")
    client.cookies.set(_CABINET_CSRF, csrf)

    response = await client.post(f"{API_V1}/auth/refresh", headers={"X-Csrf-Token": csrf})

    assert response.status_code == 401
    cleared = response.headers.get_list("set-cookie")
    assert any(c.startswith(f'{_CABINET_REFRESH}=""') for c in cleared)
    assert any(c.startswith(f'{_CABINET_CSRF}=""') for c in cleared)


async def test_dashboard_refresh_rejects_a_cabinet_session(
    client: httpx.AsyncClient, sign_in: CabinetSignIn
) -> None:
    _, issued = await _sign_in(sign_in)
    headers = _set_cookies(client, issued, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME)

    response = await client.post(f"{API_V1}/auth/refresh", headers=headers)

    assert response.status_code == 401


async def test_cabinet_refresh_rejects_a_dashboard_session(
    client: httpx.AsyncClient, sign_in: CabinetSignIn, container: AsyncContainer
) -> None:
    dashboard = await _dashboard_session(sign_in, container)
    headers = _set_cookies(client, dashboard, _CABINET_REFRESH, _CABINET_CSRF)

    response = await client.post(f"{API_V1}/auth/refresh", headers=headers)

    assert response.status_code == 401


async def test_cabinet_logout_keeps_a_dashboard_session(
    client: httpx.AsyncClient,
    sign_in: CabinetSignIn,
    container: AsyncContainer,
    session_repository: SessionRepository,
) -> None:
    dashboard = await _dashboard_session(sign_in, container)
    headers = _set_cookies(client, dashboard, _CABINET_REFRESH, _CABINET_CSRF)

    response = await client.post(f"{API_V1}/auth/logout", headers=headers)

    assert response.status_code == 204
    assert (
        await session_repository.find_by_current_hash(hash_refresh_token(dashboard.refresh_token))
        is not None
    )


async def test_dashboard_logout_keeps_a_cabinet_session(
    client: httpx.AsyncClient, sign_in: CabinetSignIn, session_repository: SessionRepository
) -> None:
    user, issued = await _sign_in(sign_in)
    headers = _set_cookies(client, issued, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME)

    response = await client.post(f"{API_V1}/auth/logout", headers=headers)

    assert response.status_code == 204
    assert len(await session_repository.list_active_by_user(user.id)) == 1


async def test_cabinet_logout_revokes_the_session(
    client: httpx.AsyncClient, sign_in: CabinetSignIn, session_repository: SessionRepository
) -> None:
    user, issued = await _sign_in(sign_in)
    headers = _set_cookies(client, issued, _CABINET_REFRESH, _CABINET_CSRF)

    response = await client.post(f"{API_V1}/auth/logout", headers=headers)

    assert response.status_code == 204
    assert await session_repository.list_active_by_user(user.id) == []


async def _enable_telegram(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_enabled=True)
        )
        await settings_repository.update_bot_settings(
            UpdateBotSettingsDto(token=_BOT_TOKEN, secret_token="s")
        )


async def _user_by_telegram_id(uow: UnitOfWork, telegram_id: int) -> UserDto:
    user = await UserRepository(uow.session).find_by_telegram_id(telegram_id)
    assert user is not None
    return user


def _signed_init_data(token: str = _BOT_TOKEN) -> str:
    fields = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": 9302, "first_name": "Bo"}),
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


async def test_cabinet_telegram_login_sets_cookies(
    client: httpx.AsyncClient, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await _enable_telegram(settings_repository, uow)

    response = await client.post(f"{API_V1}/auth/telegram", json={"init_data": _signed_init_data()})

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.cookies.get(_CABINET_REFRESH)


async def test_mini_app_sign_in_lives_seven_days(
    client: httpx.AsyncClient,
    settings_repository: SettingsRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
) -> None:
    await _enable_telegram(settings_repository, uow)

    response = await client.post(f"{API_V1}/auth/telegram", json={"init_data": _signed_init_data()})

    assert response.status_code == 200
    set_cookie = next(
        h for h in response.headers.get_list("set-cookie") if h.startswith(_CABINET_REFRESH)
    )
    max_age = int(set_cookie.split("Max-Age=")[1].split(";")[0])
    assert TTL_7D - 60 <= max_age <= TTL_7D
    async with uow:
        [session] = await session_repository.list_active_by_user(
            (await _user_by_telegram_id(uow, 9302)).id
        )
    lifetime = (session.expires_at - session.created_at).total_seconds()
    assert TTL_7D - 60 <= lifetime <= TTL_7D + 60


async def test_other_cabinet_sign_ins_keep_thirty_days(sign_in: CabinetSignIn) -> None:
    _, issued = await _sign_in(sign_in)

    remaining = (issued.expires_at - datetime_now()).total_seconds()
    assert TTL_30D - 60 <= remaining <= TTL_30D


async def test_cabinet_telegram_login_rejects_tampered_data(
    client: httpx.AsyncClient, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await _enable_telegram(settings_repository, uow)

    response = await client.post(
        f"{API_V1}/auth/telegram", json={"init_data": _signed_init_data("1:other")}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_INIT_DATA"


async def test_cabinet_telegram_login_limits_only_failures(
    client: httpx.AsyncClient, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await _enable_telegram(settings_repository, uow)
    url = f"{API_V1}/auth/telegram"

    for _ in range(5):
        bad = await client.post(url, json={"init_data": _signed_init_data("1:other")})
        assert bad.status_code == 401
    for _ in range(25):
        ok = await client.post(url, json={"init_data": _signed_init_data()})
        assert ok.status_code == 200

    for _ in range(15):
        await client.post(url, json={"init_data": _signed_init_data("1:other")})
    blocked = await client.post(url, json={"init_data": _signed_init_data()})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"


async def test_telegram_signin_unknown_token_is_failure_limited(
    client: httpx.AsyncClient, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await _enable_telegram(settings_repository, uow)
    url = f"{API_V1}/auth/telegram/signin"

    for _ in range(20):
        response = await client.post(url, json={"token": "x" * 43})
        assert response.status_code == 401
        assert response.json()["code"] == "DEEPLINK_EXPIRED"
    assert (await client.post(url, json={"token": "x" * 43})).status_code == 429


async def test_methods_has_no_per_route_limit(client: httpx.AsyncClient) -> None:
    for _ in range(40):
        assert (await client.get(f"{API_V1}/auth/methods")).status_code == 200
