from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from pydantic import SecretStr

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

_SECRET = "s3cret"
_PROXIED = {"X-Cabinet-Proxy-Secret": _SECRET, "X-Cabinet-Client-IP": "203.0.113.9"}
_PASSWORD = "correct-horse-battery"


@pytest.fixture
async def proxied_client(
    config: AppConfig, container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config.model_copy(update={"cabinet_proxy_secret": SecretStr(_SECRET)}))
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _user(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig, login: str, role: Role
) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password(_PASSWORD, config.crypt_key.get_secret_value()),
                name=login,
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    return user


async def _token(
    user_id: int,
    audience: SessionAudience,
    session_repository: SessionRepository,
    config: AppConfig,
) -> str:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(f"proxy-guard-{user_id}-{audience.value}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            audience=audience,
        )
    )
    return create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())


async def test_dashboard_sign_in_is_refused_through_the_proxy(
    proxied_client: httpx.AsyncClient,
) -> None:
    for method, path, body in (
        ("POST", f"{API_V1}/auth/login", {"login": "owner", "password": _PASSWORD}),
        ("POST", f"{API_V1}/auth/bootstrap", {"login": "owner", "password": _PASSWORD}),
        ("GET", f"{API_V1}/auth/passkeys/authenticate/options", None),
    ):
        response = await proxied_client.request(method, path, json=body, headers=_PROXIED)
        assert response.status_code == 403, path
        assert response.json()["code"] == "PROXY_DASHBOARD_FORBIDDEN", path


async def test_a_dashboard_token_is_refused_through_the_proxy(
    proxied_client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _user(user_repository, uow, config, "proxyowner", Role.OWNER)
    token = await _token(owner.id, SessionAudience.DASHBOARD, session_repository, config)
    bearer = {"Authorization": f"Bearer {token}"}

    direct = await proxied_client.get(f"{API_V1}/admins", headers=bearer)
    assert direct.status_code == 200

    proxied = await proxied_client.get(f"{API_V1}/admins", headers={**bearer, **_PROXIED})
    assert proxied.status_code == 403
    assert proxied.json()["code"] == "PROXY_DASHBOARD_FORBIDDEN"

    forged = await proxied_client.get(
        f"{API_V1}/admins", headers={**bearer, "X-Cabinet-Proxy-Secret": "wrong"}
    )
    assert forged.status_code == 200


async def test_a_cabinet_session_still_cannot_reach_admin_routes(
    proxied_client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    staff = await _user(user_repository, uow, config, "cabinetstaff", Role.OWNER)
    token = await _token(staff.id, SessionAudience.CABINET, session_repository, config)

    response = await proxied_client.get(
        f"{API_V1}/admins", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "SESSION_AUDIENCE_MISMATCH"


async def test_password_login_refuses_a_customer_like_a_wrong_password(
    client: httpx.AsyncClient, user_repository: UserRepository, uow: UnitOfWork, config: AppConfig
) -> None:
    await _user(user_repository, uow, config, "plaincustomer", Role.USER)

    response = await client.post(
        f"{API_V1}/auth/login", json={"login": "plaincustomer", "password": _PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


async def test_customer_and_staff_routes_through_the_proxy_need_a_cabinet_session(
    proxied_client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _user(user_repository, uow, config, "proxycustomerowner", Role.OWNER)
    dashboard = await _token(owner.id, SessionAudience.DASHBOARD, session_repository, config)
    cabinet = await _token(owner.id, SessionAudience.CABINET, session_repository, config)

    for path in (f"{API_V1}/subscriptions/me", f"{API_V1}/users/me"):
        refused = await proxied_client.get(
            path, headers={"Authorization": f"Bearer {dashboard}", **_PROXIED}
        )
        assert refused.status_code == 403, path
        assert refused.json()["code"] == "PROXY_DASHBOARD_FORBIDDEN", path

    allowed = await proxied_client.get(
        f"{API_V1}/subscriptions/me", headers={"Authorization": f"Bearer {cabinet}", **_PROXIED}
    )
    assert allowed.status_code == 200
