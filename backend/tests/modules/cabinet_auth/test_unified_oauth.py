from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from pydantic import SecretStr
from redis.asyncio import Redis

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.config.cabinet import CabinetConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, OAuthProvider, Role
from app.modules.oauth import (
    OAuthFlowPurpose,
    OAuthIdentityRepository,
    OAuthProfile,
    OAuthStateStore,
    binding_matches,
    new_binding,
)
from app.modules.oauth.dto import CreateOAuthIdentityDto
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_peek_purpose_does_not_spend_the_state(redis: Redis) -> None:
    store = OAuthStateStore(redis)
    state = await store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
    )
    assert await store.peek_purpose(state) is OAuthFlowPurpose.LOGIN
    assert await store.consume(state) is not None
    assert await store.peek_purpose(state) is None


def test_binding_helpers() -> None:
    binding, digest = new_binding()
    assert binding_matches(binding, digest)
    assert not binding_matches("other", digest)
    assert not binding_matches(None, digest)
    assert not binding_matches(binding, None)


async def test_callback_without_the_binding_cookie_is_an_invalid_state(
    client: httpx.AsyncClient, redis: Redis
) -> None:
    _, digest = new_binding()
    state = await OAuthStateStore(redis).create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=digest,
    )

    response = await client.post(
        f"{API_V1}/auth/oauth/github/callback", json={"code": "c", "state": state}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "OAUTH_STATE_INVALID"


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


async def test_dashboard_oauth_is_refused_through_the_proxy(
    proxied_client: httpx.AsyncClient, redis: Redis
) -> None:
    proxied = {"X-Cabinet-Proxy-Secret": "s3cret"}
    authorize = await proxied_client.post(
        f"{API_V1}/auth/oauth/github/authorize", json={"audience": "dashboard"}, headers=proxied
    )
    assert authorize.status_code == 403
    assert authorize.json()["code"] == "PROXY_DASHBOARD_FORBIDDEN"

    binding, digest = new_binding()
    state = await OAuthStateStore(redis).create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=digest,
    )
    proxied_client.cookies.set("oauth_binding", binding)
    callback = await proxied_client.post(
        f"{API_V1}/auth/oauth/github/callback",
        json={"code": "c", "state": state},
        headers=proxied,
    )
    assert callback.status_code == 403
    assert callback.json()["code"] == "PROXY_DASHBOARD_FORBIDDEN"


async def test_dashboard_oauth_sign_in_sets_the_dashboard_cookies(
    client: httpx.AsyncClient,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    uow: UnitOfWork,
) -> None:
    class _FakeClient:
        async def fetch_identity(self, *_: object) -> OAuthProfile:
            return OAuthProfile(external_id="gh-owner", login="owner")

    monkeypatch.setattr(
        "app.modules.oauth.usecases.oauth_login_callback.get_oauth_client",
        lambda *_, **__: _FakeClient(),
    )
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(login="oauthowner", name="Owner", role=Role.OWNER, language=Locale.EN)
        )
        await oauth_identity_repository.create(
            CreateOAuthIdentityDto(
                user_id=owner.id,
                provider=OAuthProvider.GITHUB,
                external_id="gh-owner",
                external_login="owner",
            )
        )
    binding, digest = new_binding()
    state = await OAuthStateStore(redis).create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=digest,
    )
    client.cookies.set("oauth_binding", binding)

    response = await client.post(
        f"{API_V1}/auth/oauth/github/callback", json={"code": "c", "state": state}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["id"] == owner.id
    assert body["login"] == "oauthowner" and body["role"] == Role.OWNER
    cookies = response.headers.get_list("set-cookie")
    refresh = next(c for c in cookies if c.startswith("refresh_token="))
    assert "samesite=lax" in refresh.lower() and "path=/api/v1/auth" in refresh.lower()
    assert any(c.startswith("csrf_token=") for c in cookies)
    assert not any(c.startswith("cabinet_refresh_token=") for c in cookies)
    assert any(c.startswith('oauth_binding=""') for c in cookies)
