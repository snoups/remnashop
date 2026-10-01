from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncIterator, Final

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1, REFRESH_COOKIE_NAME
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.providers import get_module_providers
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

_PASSWORD: Final[str] = "Sup3rSecurePassword12345"
_SVG_LOGO: Final[bytes] = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"></svg>'


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


@pytest.fixture
def app_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


@pytest.fixture
async def test_container(
    session: AsyncSession, app_config: AppConfig
) -> AsyncIterator[AsyncContainer]:
    # Mirrors create_api_container() so every router below resolves its real
    # usecase graph; _TestSessionProvider goes last to win the AsyncSession.
    providers = [
        *get_core_providers(),
        *get_module_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: app_config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    app_config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(app_config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _create_user(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig, role: Role, login: str
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


async def _auth_headers(
    user: UserDto, session_repository: SessionRepository, config: AppConfig
) -> dict[str, str]:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"refresh-{user.id}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "critical-owner")
    return await _auth_headers(owner, session_repository, config)


@pytest.fixture
async def admin_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    admin = await _create_user(user_repository, uow, config, Role.ADMIN, "critical-admin")
    return await _auth_headers(admin, session_repository, config)


# --- sessionless: auth ---


async def test_status_allows_login_once_an_owner_exists(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.get(f"{API_V1}/auth/status")

    assert response.status_code == 200
    body = response.json()
    assert body["is_login_allowed"] is True
    assert body["is_register_allowed"] is False


async def test_login_issues_access_token_and_httponly_refresh_cookie(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_V1}/auth/login", json={"login": "critical-owner", "password": _PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    refresh_cookie = next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(f"{REFRESH_COOKIE_NAME}=")
    )
    assert "httponly" in refresh_cookie.lower()


async def test_login_failure_does_not_reveal_whether_login_exists(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    wrong_password = await client.post(
        f"{API_V1}/auth/login", json={"login": "critical-owner", "password": "wrong"}
    )
    unknown_login = await client.post(
        f"{API_V1}/auth/login", json={"login": "nobody-here", "password": "wrong"}
    )

    assert wrong_password.status_code == unknown_login.status_code == 401
    assert wrong_password.json() == unknown_login.json()
    assert REFRESH_COOKIE_NAME not in wrong_password.cookies


# --- sessionless: oauth / passkeys ---


async def test_oauth_authorize_rejects_unconfigured_provider(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/auth/oauth/GITHUB/authorize")

    assert response.status_code == 400


async def test_oauth_callback_rejects_unknown_state(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"{API_V1}/auth/oauth/GITHUB/callback", json={"code": "code", "state": "forged"}
    )

    assert response.status_code == 401
    assert REFRESH_COOKIE_NAME not in response.cookies


async def test_passkey_options_rejected_while_passkeys_disabled(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/auth/passkeys/authenticate/options")

    assert response.status_code == 400


async def test_passkey_verify_rejects_garbage_credential(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"{API_V1}/auth/passkeys/authenticate/verify", json={"credential": {"id": "x"}}
    )

    assert response.status_code == 401
    assert REFRESH_COOKIE_NAME not in response.cookies


# --- sessionless: appearance / emoji ---


async def test_public_appearance_needs_no_session(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/appearance")

    assert response.status_code == 200
    assert response.json()["has_logo"] is False


async def test_public_appearance_images_404_when_unset(client: httpx.AsyncClient) -> None:
    for kind in ("logo", "favicon"):
        response = await client.get(f"{API_V1}/appearance/{kind}")
        assert response.status_code == 404
        assert response.json()["detail"] != "Not Found"  # usecase miss, not an unrouted path


async def test_public_logo_is_served_sandboxed(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    upload = await client.put(
        f"{API_V1}/settings/appearance/logo",
        files={"file": ("logo.svg", _SVG_LOGO, "image/svg+xml")},
        headers=owner_headers,
    )
    assert upload.status_code == 200

    response = await client.get(f"{API_V1}/appearance/logo")

    assert response.status_code == 200
    assert response.content == _SVG_LOGO
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("kind", ["thumbnails", "animations"])
async def test_emoji_media_404_for_unknown_id_without_session(
    client: httpx.AsyncClient, kind: str
) -> None:
    response = await client.get(f"{API_V1}/emoji-packs/{kind}/5368324170671202286")

    assert response.status_code == 404
    assert response.json()["detail"] != "Not Found"


# --- customer: promocode activation ---


async def test_promocode_activate_requires_session(client: httpx.AsyncClient) -> None:
    response = await client.post(f"{API_V1}/promocodes/activations", json={"code": "ANY"})

    assert response.status_code == 401


async def test_promocode_activate_rejects_api_token(
    client: httpx.AsyncClient, api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> None:
    # a token has no customer row behind it -- get_current_user must refuse it
    secret = "critical-routes-token-secret"
    async with uow:
        await api_token_repository.create(
            CreateApiTokenDto(
                name="critical-routes",
                permissions=[Permission.PROMOCODES_VIEW],
                token_hash=hash_refresh_token(secret),
                created_by_user_id=None,
                expires_at=None,
            )
        )
        await uow.commit()

    response = await client.post(
        f"{API_V1}/promocodes/activations",
        json={"code": "ANY"},
        headers={"Authorization": f"Bearer {secret}"},
    )

    assert response.status_code == 403


async def test_promocode_activate_unknown_code_is_404(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    customer = await _create_user(user_repository, uow, config, Role.USER, "critical-customer")
    headers = await _auth_headers(customer, session_repository, config)

    response = await client.post(
        f"{API_V1}/promocodes/activations", json={"code": "NO-SUCH-CODE"}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] != "Not Found"


# --- secrets never come back out ---


async def test_bot_settings_never_return_the_token(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    token = "123456789:AAH-critical-routes-bot-token"
    update = await client.patch(
        f"{API_V1}/settings/bot",
        json={"token": token, "secret_token": "critical-webhook-secret"},
        headers=owner_headers,
    )
    read = await client.get(f"{API_V1}/settings/bot", headers=owner_headers)

    assert update.status_code == read.status_code == 200
    assert read.json()["is_configured"] is True
    for response in (update, read):
        assert token not in response.text
        assert "critical-webhook-secret" not in response.text


async def test_bot_settings_forbidden_for_customer(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    customer = await _create_user(user_repository, uow, config, Role.USER, "critical-customer2")
    headers = await _auth_headers(customer, session_repository, config)

    response = await client.get(f"{API_V1}/settings/bot", headers=headers)

    assert response.status_code == 403


async def test_oauth_settings_never_return_client_secrets(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    secret = "critical-github-client-secret"
    update = await client.patch(
        f"{API_V1}/settings/oauth",
        json={"github_client_id": "critical-client-id", "github_client_secret": secret},
        headers=owner_headers,
    )
    read = await client.get(f"{API_V1}/settings/oauth", headers=owner_headers)

    assert update.status_code == read.status_code == 200
    assert read.json()["is_github_configured"] is True
    assert secret not in update.text
    assert secret not in read.text


async def test_gateway_settings_never_return_secret_fields(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    secret = "live_critical_routes_api_key"
    update = await client.put(
        f"{API_V1}/gateways/YOOKASSA/settings",
        json={"values": {"shop_id": "123456", "api_key": secret}},
        headers=owner_headers,
    )
    read = await client.get(f"{API_V1}/gateways", headers=owner_headers)

    assert update.status_code == read.status_code == 200
    assert secret not in update.text
    assert secret not in read.text


async def test_gateway_settings_forbidden_for_plain_admin(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await client.put(
        f"{API_V1}/gateways/YOOKASSA/settings",
        json={"values": {"shop_id": "123456", "api_key": "x"}},
        headers=admin_headers,
    )

    assert response.status_code == 403


# --- OWNER-only pricing ---


async def test_currency_rate_owner_only(
    client: httpx.AsyncClient, owner_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    payload = {"rate": "90", "rounding_mode": "INTEGER", "min_amount": "1"}

    admin_response = await client.put(
        f"{API_V1}/pricing/rates/RUB", json=payload, headers=admin_headers
    )
    owner_response = await client.put(
        f"{API_V1}/pricing/rates/RUB", json=payload, headers=owner_headers
    )

    assert admin_response.status_code == 403
    assert owner_response.status_code == 200


async def test_anchor_switch_forbidden_for_plain_admin(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_V1}/pricing/actions/switch-anchor", json={"new_anchor": "RUB"}, headers=admin_headers
    )

    assert response.status_code == 403
