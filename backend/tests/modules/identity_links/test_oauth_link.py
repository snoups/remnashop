from typing import Optional

import httpx
import pytest

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.modules.auth.repository import SessionRepository
from app.modules.oauth import (
    OAuthFlowPurpose,
    OAuthIdentityRepository,
    OAuthProfile,
    OAuthStateStore,
    new_binding,
)
from app.modules.oauth.dto import CreateOAuthIdentityDto
from app.modules.settings.dto import UpdateCabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.identity_links.conftest import bearer

LINK = f"{API_V1}/users/me/identities/oauth"
LOGIN = f"{API_V1}/auth/oauth"


class _FakeClient:
    requires_pkce = True

    def __init__(self, profile: OAuthProfile) -> None:
        self._profile = profile

    async def authorization_url(
        self, redirect_uri: str, state: str, code_verifier: Optional[str]
    ) -> str:
        return f"https://idp.example/auth?redirect_uri={redirect_uri}&state={state}"

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: Optional[str]
    ) -> OAuthProfile:
        return self._profile


@pytest.fixture
def profile_holder(monkeypatch: pytest.MonkeyPatch, config: AppConfig) -> dict[str, OAuthProfile]:
    holder: dict[str, OAuthProfile] = {}

    def _fake(provider: OAuthProvider, settings: object, *, require_enabled: bool = True) -> object:
        return _FakeClient(holder["profile"])

    for module in ("cabinet_oauth_authorize", "cabinet_oauth_callback"):
        monkeypatch.setattr(f"app.modules.cabinet_auth.usecases.{module}.get_oauth_client", _fake)
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    return holder


@pytest.fixture(autouse=True)
async def _enable_providers(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_oauth_enabled=True, google_enabled=True)
        )


@pytest.fixture
async def me(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="me"))


@pytest.fixture
async def headers(
    me: UserDto, session_repository: SessionRepository, config: AppConfig
) -> dict[str, str]:
    return await bearer(me.id, session_repository, config)


async def _link(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    holder: dict[str, OAuthProfile],
    provider: str,
    profile: OAuthProfile,
) -> httpx.Response:
    holder["profile"] = profile
    authorized = await client.post(f"{LINK}/{provider}/authorize", headers=headers)
    assert authorized.status_code == 200, authorized.text
    state = authorized.json()["url"].rsplit("state=", 1)[1]
    return await client.post(
        f"{LINK}/{provider}/callback", json={"code": "c", "state": state}, headers=headers
    )


async def test_link_google_free(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    me: UserDto,
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    profile = OAuthProfile(
        external_id="g-free", login="ann", email="Free@Gmail.com", email_verified=True
    )
    response = await _link(client, headers, profile_holder, "google", profile)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "linked"
    assert not client.cookies.get("oauth_binding")
    identities = await oauth_identity_repository.list_by_user(me.id)
    assert [(i.provider, i.external_id) for i in identities] == [(OAuthProvider.GOOGLE, "g-free")]
    linked = await user_repository.find_by_id(me.id)
    assert linked is not None and linked.email == "free@gmail.com"


async def test_link_google_unverified_email_not_written(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    me: UserDto,
    user_repository: UserRepository,
) -> None:
    profile = OAuthProfile(external_id="g-unv", login=None, email="unv@gmail.com")
    response = await _link(client, headers, profile_holder, "google", profile)

    assert response.json()["status"] == "linked"
    linked = await user_repository.find_by_id(me.id)
    assert linked is not None and linked.email is None


async def test_link_google_foreign_email_ignored(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    me: UserDto,
    user_repository: UserRepository,
) -> None:
    await user_repository.create(CreateUserDto(name="other", email="taken@gmail.com"))
    profile = OAuthProfile(
        external_id="g-taken", login=None, email="taken@gmail.com", email_verified=True
    )
    response = await _link(client, headers, profile_holder, "google", profile)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "linked"
    linked = await user_repository.find_by_id(me.id)
    assert linked is not None and linked.email is None


async def test_link_telegram_oidc(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    me: UserDto,
    user_repository: UserRepository,
) -> None:
    profile = OAuthProfile(external_id="8118", login="ann", name="Ann")
    response = await _link(client, headers, profile_holder, "telegram", profile)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "linked"
    linked = await user_repository.find_by_id(me.id)
    assert linked is not None and linked.telegram_id == 8118


async def test_link_google_foreign_identity_merge_required(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        other = await user_repository.create(CreateUserDto(name="other"))
        await oauth_identity_repository.create(
            CreateOAuthIdentityDto(
                user_id=other.id,
                provider=OAuthProvider.GOOGLE,
                external_id="g-other",
                external_login="other",
            )
        )
    profile = OAuthProfile(external_id="g-other", login="other")
    response = await _link(client, headers, profile_holder, "google", profile)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "merge_required"
    assert body["merge_token"]
    assert {"kind": "GOOGLE", "linked": True, "label": "other", "editable": True} in body["other"][
        "identities"
    ]


async def test_login_state_rejected_by_link(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    oauth_state_store: OAuthStateStore,
    me: UserDto,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g-login", login=None)
    binding, digest = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.GOOGLE,
        purpose=OAuthFlowPurpose.CABINET_LOGIN,
        user_id=None,
        code_verifier="v",
        binding_hash=digest,
    )
    client.cookies.set("oauth_binding", binding)

    response = await client.post(
        f"{LINK}/google/callback", json={"code": "c", "state": state}, headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "OAUTH_STATE_INVALID"
    assert await oauth_identity_repository.list_by_user(me.id) == []


async def test_link_state_rejected_by_login(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    user_repository: UserRepository,
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g-link", login=None, name="Link")
    authorized = await client.post(f"{LINK}/google/authorize", headers=headers)
    assert authorized.status_code == 200
    state = authorized.json()["url"].rsplit("state=", 1)[1]
    binding = client.cookies.get("oauth_binding")
    assert binding
    client.cookies.clear()
    client.cookies.set("oauth_binding", binding)

    response = await client.post(f"{LOGIN}/google/callback", json={"code": "c", "state": state})

    assert response.status_code == 401
    assert response.json()["code"] == "OAUTH_STATE_INVALID"
    assert not client.cookies.get("cabinet_refresh_token")


async def test_link_state_of_other_user_rejected(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    oauth_state_store: OAuthStateStore,
    me: UserDto,
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g-x", login=None)
    binding, digest = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.GOOGLE,
        purpose=OAuthFlowPurpose.CABINET_CONNECT,
        user_id=me.id + 1000,
        code_verifier="v",
        binding_hash=digest,
    )
    client.cookies.set("oauth_binding", binding)

    response = await client.post(
        f"{LINK}/google/callback", json={"code": "c", "state": state}, headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "OAUTH_STATE_INVALID"


async def test_missing_binding_rejected(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g-nb", login=None)
    authorized = await client.post(f"{LINK}/google/authorize", headers=headers)
    set_cookie = authorized.headers["set-cookie"]
    # the sign-in cookie's /auth path would never reach the link callback
    assert "httponly" in set_cookie.lower()
    assert f"Path={LINK}" in set_cookie
    state = authorized.json()["url"].rsplit("state=", 1)[1]
    client.cookies.clear()

    response = await client.post(
        f"{LINK}/google/callback", json={"code": "c", "state": state}, headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "OAUTH_STATE_INVALID"
    assert 'oauth_binding=""' in response.headers["set-cookie"]


async def test_oauth_link_routes_need_a_session(client: httpx.AsyncClient) -> None:
    assert (await client.post(f"{LINK}/google/authorize")).status_code == 401
    callback = await client.post(f"{LINK}/google/callback", json={"code": "c", "state": "s"})
    assert callback.status_code == 401


async def test_link_telegram_owned_by_other_account_then_merge(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    profile_holder: dict[str, OAuthProfile],
    me: UserDto,
    user_repository: UserRepository,
) -> None:
    other = await user_repository.create(CreateUserDto(name="other", telegram_id=8200))
    profile = OAuthProfile(external_id="8200", login="ann", name="Ann")
    response = await _link(client, headers, profile_holder, "telegram", profile)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "merge_required"

    merged = await client.post(
        f"{API_V1}/users/me/merge", json={"merge_token": body["merge_token"]}, headers=headers
    )

    assert merged.status_code == 200, merged.text
    mine = await user_repository.find_by_id(me.id)
    assert mine is not None and mine.telegram_id == 8200
    gone = await user_repository.find_by_id(other.id)
    assert gone is None or gone.telegram_id is None
