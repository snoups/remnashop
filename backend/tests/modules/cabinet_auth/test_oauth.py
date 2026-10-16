from typing import Optional

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.modules.blacklist import BlacklistRepository
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.cabinet_auth.usecases import (
    CabinetOAuthAuthorizeUseCase,
    CabinetOAuthCallbackUseCase,
)
from app.modules.oauth import (
    OAuthFlowPurpose,
    OAuthIdentityRepository,
    OAuthProfile,
    OAuthStateStore,
    get_oauth_client,
)
from app.modules.oauth.dto import CreateOAuthIdentityDto
from app.modules.oauth.usecases import OAuthConnectAuthorizeUseCase, OAuthLoginAuthorizeUseCase
from app.modules.settings import SettingsRepository, UpdateOAuthSettingsDto
from app.modules.settings.dto import UpdateCabinetAuthSettingsDto
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

_IP = "203.0.113.1"
_CABINET_URL = "https://cabinet.example.com/"


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
        assert code_verifier
        return self._profile


@pytest.fixture
def cabinet_config(config: AppConfig) -> AppConfig:
    return config.model_copy(update={"web_cabinet_url": _CABINET_URL})


@pytest.fixture
def profile_holder(monkeypatch: pytest.MonkeyPatch) -> dict[str, OAuthProfile]:
    holder: dict[str, OAuthProfile] = {}

    def _fake(provider: OAuthProvider, settings: object, *, require_enabled: bool = True) -> object:
        return _FakeClient(holder["profile"])

    for module in ("cabinet_oauth_authorize", "cabinet_oauth_callback"):
        monkeypatch.setattr(f"app.modules.cabinet_auth.usecases.{module}.get_oauth_client", _fake)
    return holder


@pytest.fixture
def authorize(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    cabinet_config: AppConfig,
    uow: UnitOfWork,
) -> CabinetOAuthAuthorizeUseCase:
    return CabinetOAuthAuthorizeUseCase(settings_repository, oauth_state_store, cabinet_config, uow)


@pytest.fixture
def callback(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    sign_in: CabinetSignIn,
    cabinet_config: AppConfig,
    uow: UnitOfWork,
) -> CabinetOAuthCallbackUseCase:
    return CabinetOAuthCallbackUseCase(
        settings_repository, oauth_state_store, sign_in, cabinet_config, uow
    )


@pytest.fixture(autouse=True)
async def _enable_providers(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_enabled=True, google_enabled=True)
        )


async def _sign_in_via(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    provider: OAuthProvider,
    profile: OAuthProfile,
    codes: Optional[InviteCodesDto] = None,
) -> UserDto:
    profile_holder["profile"] = profile
    url, binding = await authorize.execute(provider, codes or InviteCodesDto())
    state = url.rsplit("state=", 1)[1]
    user, _ = await callback.execute(provider, "code", state, binding, _IP, "ua")
    return user


async def test_known_identity_signs_in_to_its_user(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Ann"))
        await oauth_identity_repository.create(
            CreateOAuthIdentityDto(
                user_id=existing.id,
                provider=OAuthProvider.GOOGLE,
                external_id="g1",
                external_login=None,
            )
        )
    user = await _sign_in_via(
        authorize,
        callback,
        profile_holder,
        OAuthProvider.GOOGLE,
        OAuthProfile(external_id="g1", login=None, email="x@example.com", email_verified=True),
    )
    assert user.id == existing.id


async def test_verified_email_links_identity_to_existing_user(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Ann", email="ann@example.com"))
    user = await _sign_in_via(
        authorize,
        callback,
        profile_holder,
        OAuthProvider.GOOGLE,
        OAuthProfile(external_id="g2", login=None, email="Ann@Example.com", email_verified=True),
    )
    assert user.id == existing.id
    async with uow:
        identity = await oauth_identity_repository.get_by_provider_external_id(
            OAuthProvider.GOOGLE, "g2"
        )
    assert identity is not None and identity.user_id == existing.id


async def test_unverified_email_creates_new_client_without_email(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Ann", email="ann@example.com"))
    user = await _sign_in_via(
        authorize,
        callback,
        profile_holder,
        OAuthProvider.GOOGLE,
        OAuthProfile(external_id="g3", login=None, email="ann@example.com", email_verified=False),
    )
    assert user.id != existing.id and user.email is None
    async with uow:
        identity = await oauth_identity_repository.get_by_provider_external_id(
            OAuthProvider.GOOGLE, "g3"
        )
    assert identity is not None and identity.user_id == user.id


async def test_new_email_registers_client(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    session: AsyncSession,
) -> None:
    user = await _sign_in_via(
        authorize,
        callback,
        profile_holder,
        OAuthProvider.GOOGLE,
        OAuthProfile(
            external_id="g4", login=None, name="New", email="new@example.com", email_verified=True
        ),
    )
    assert user.email == "new@example.com" and user.name == "New"
    [event] = await session.scalars(
        select(EventOutboxEntry).where(EventOutboxEntry.event_type == "CabinetUserRegisteredEvent")
    )
    assert event.payload["method"] == "GOOGLE"


async def test_blacklisted_verified_email_is_blocked(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await blacklist_repository.add_entry(BlacklistKind.EMAIL, "bad@example.com")
    with pytest.raises(PermissionDeniedError) as error:
        await _sign_in_via(
            authorize,
            callback,
            profile_holder,
            OAuthProvider.GOOGLE,
            OAuthProfile(
                external_id="g5", login=None, email="bad@example.com", email_verified=True
            ),
        )
    assert error.value.code is ErrorCode.USER_BLOCKED


async def test_telegram_matches_by_telegram_id_without_identity_rows(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="Bot", telegram_id=4242))
    user = await _sign_in_via(
        authorize,
        callback,
        profile_holder,
        OAuthProvider.TELEGRAM,
        OAuthProfile(external_id="4242", login="bot", name="Bot"),
    )
    assert user.id == existing.id
    async with uow:
        assert await oauth_identity_repository.list_by_user(existing.id) == []


async def test_dashboard_state_is_rejected(
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    oauth_state_store: OAuthStateStore,
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g6", login=None)
    state = await oauth_state_store.create(
        provider=OAuthProvider.GOOGLE,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier="v",
    )
    with pytest.raises(AuthenticationError) as error:
        await callback.execute(OAuthProvider.GOOGLE, "code", state, "binding", _IP, None)
    assert error.value.code is ErrorCode.OAUTH_STATE_INVALID


@pytest.mark.parametrize("binding", [None, "", "someone-else"])
async def test_missing_or_foreign_binding_is_rejected(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    binding: Optional[str],
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g7", login=None)
    url, _ = await authorize.execute(OAuthProvider.GOOGLE, InviteCodesDto())
    with pytest.raises(AuthenticationError) as error:
        await callback.execute(
            OAuthProvider.GOOGLE, "code", url.rsplit("state=", 1)[1], binding, _IP, None
        )
    assert error.value.code is ErrorCode.OAUTH_STATE_INVALID


async def test_state_of_another_provider_is_rejected(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g8", login=None)
    url, binding = await authorize.execute(OAuthProvider.GOOGLE, InviteCodesDto())
    with pytest.raises(AuthenticationError) as error:
        await callback.execute(
            OAuthProvider.TELEGRAM, "code", url.rsplit("state=", 1)[1], binding, _IP, None
        )
    assert error.value.code is ErrorCode.OAUTH_STATE_INVALID


async def test_authorize_builds_cabinet_redirect_uri(
    authorize: CabinetOAuthAuthorizeUseCase, profile_holder: dict[str, OAuthProfile]
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g9", login=None)
    url, binding = await authorize.execute(OAuthProvider.GOOGLE, InviteCodesDto())
    assert "redirect_uri=https://cabinet.example.com/login/callback/google&" in url
    assert binding


async def test_authorize_rejects_provider_disabled_for_cabinet(
    authorize: CabinetOAuthAuthorizeUseCase, profile_holder: dict[str, OAuthProfile]
) -> None:
    with pytest.raises(AuthenticationError) as error:
        await authorize.execute(OAuthProvider.YANDEX, InviteCodesDto())
    assert error.value.code is ErrorCode.OAUTH_PROVIDER_DISABLED


async def test_authorize_without_cabinet_url_is_not_configured(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    config: AppConfig,
    uow: UnitOfWork,
) -> None:
    use_case = CabinetOAuthAuthorizeUseCase(
        settings_repository,
        oauth_state_store,
        config.model_copy(update={"web_cabinet_url": ""}),
        uow,
    )
    with pytest.raises(AuthenticationError) as error:
        await use_case.execute(OAuthProvider.GOOGLE, InviteCodesDto())
    assert error.value.code is ErrorCode.OAUTH_PROVIDER_NOT_CONFIGURED


@pytest.mark.parametrize("provider", [OAuthProvider.GOOGLE, OAuthProvider.YANDEX])
async def test_dashboard_authorize_rejects_cabinet_only_providers(
    provider: OAuthProvider,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    config: AppConfig,
    uow: UnitOfWork,
) -> None:
    login = OAuthLoginAuthorizeUseCase(settings_repository, oauth_state_store, config, uow)
    connect = OAuthConnectAuthorizeUseCase(settings_repository, oauth_state_store, config, uow)
    admin = UserDto.model_construct(id=1)
    with pytest.raises(AuthenticationError) as login_error:
        await login.execute(provider)
    with pytest.raises(AuthenticationError) as connect_error:
        await connect._execute(admin, provider)
    assert login_error.value.code is ErrorCode.OAUTH_PROVIDER_UNSUPPORTED
    assert connect_error.value.code is ErrorCode.OAUTH_PROVIDER_UNSUPPORTED


async def test_client_for_dashboard_disabled_telegram_needs_require_enabled_false(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await settings_repository.update_oauth_settings(
            UpdateOAuthSettingsDto(
                telegram_client_id="1", telegram_client_secret="s", telegram_enabled=False
            )
        )
        settings = await settings_repository.get_oauth_settings()
    assert get_oauth_client(OAuthProvider.TELEGRAM, settings, require_enabled=False)
    with pytest.raises(AuthenticationError) as error:
        get_oauth_client(OAuthProvider.TELEGRAM, settings)
    assert error.value.code is ErrorCode.OAUTH_PROVIDER_DISABLED


async def test_email_match_keeps_existing_identity_of_the_provider(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    user_repository: UserRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="U", email="b@corp.example"))
        await oauth_identity_repository.create(
            CreateOAuthIdentityDto(
                user_id=existing.id,
                provider=OAuthProvider.GOOGLE,
                external_id="g1",
                external_login=None,
            )
        )
    user = await _sign_in_via(
        authorize,
        callback,
        profile_holder,
        OAuthProvider.GOOGLE,
        OAuthProfile(external_id="g2", login=None, email="b@corp.example", email_verified=True),
    )
    assert user.id == existing.id
    async with uow:
        [identity] = await oauth_identity_repository.list_by_user(existing.id)
    assert identity.external_id == "g1"
    again = await _sign_in_via(
        authorize,
        callback,
        profile_holder,
        OAuthProvider.GOOGLE,
        OAuthProfile(external_id="g1", login=None),
    )
    assert again.id == existing.id


async def test_callback_rechecks_provider_enabled(
    authorize: CabinetOAuthAuthorizeUseCase,
    callback: CabinetOAuthCallbackUseCase,
    profile_holder: dict[str, OAuthProfile],
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    profile_holder["profile"] = OAuthProfile(external_id="g10", login=None)
    url, binding = await authorize.execute(OAuthProvider.GOOGLE, InviteCodesDto())
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(google_enabled=False)
        )
    with pytest.raises(AuthenticationError) as error:
        await callback.execute(
            OAuthProvider.GOOGLE, "code", url.rsplit("state=", 1)[1], binding, _IP, None
        )
    assert error.value.code is ErrorCode.OAUTH_PROVIDER_DISABLED


async def test_oauth_routes_end_to_end(
    client: httpx.AsyncClient,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
    profile_holder: dict[str, OAuthProfile],
) -> None:
    monkeypatch.setattr(config, "web_cabinet_url", _CABINET_URL)
    profile_holder["profile"] = OAuthProfile(external_id="g11", login=None, name="Route")
    base = "/api/v1/auth/oauth/google"

    authorized = await client.post(f"{base}/authorize", json={"audience": "cabinet"})
    assert authorized.status_code == 200
    assert "httponly" in authorized.headers["set-cookie"].lower()
    state = authorized.json()["url"].rsplit("state=", 1)[1]
    binding = client.cookies.pop("oauth_binding")

    missing = await client.post(f"{base}/callback", json={"code": "c", "state": state})
    assert missing.status_code == 401 and missing.json()["code"] == "OAUTH_STATE_INVALID"

    # the failed attempt consumed the state; start over
    authorized = await client.post(f"{base}/authorize", json={"audience": "cabinet"})
    state = authorized.json()["url"].rsplit("state=", 1)[1]
    assert client.cookies.get("oauth_binding")
    done = await client.post(f"{base}/callback", json={"code": "c", "state": state})
    assert done.status_code == 200 and done.json()["access_token"]
    assert client.cookies.get("cabinet_refresh_token")
    assert not client.cookies.get("oauth_binding")
    assert binding


async def test_failed_callback_deletes_the_binding_cookie(
    client: httpx.AsyncClient, config: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "web_cabinet_url", _CABINET_URL)
    base = "/api/v1/auth/oauth/google"
    await client.post(f"{base}/authorize", json={"audience": "cabinet"})

    failed = await client.post(f"{base}/callback", json={"code": "c", "state": "wrong"})

    assert failed.status_code == 401 and failed.json()["code"] == "OAUTH_STATE_INVALID"
    assert 'oauth_binding=""' in failed.headers["set-cookie"]
    assert not client.cookies.get("oauth_binding")
