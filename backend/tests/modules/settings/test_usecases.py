from io import BytesIO
from pathlib import Path
from typing import Optional

import pytest
from aiogram.methods import SetMyCommands
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageKind, AppearanceTarget, Locale, OAuthProvider, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.modules.oauth.dto import CreateOAuthIdentityDto
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.settings import command_translations
from app.modules.settings.bot_commands import BOT_COMMANDS, BotCommand
from app.modules.settings.dto import (
    BotStatusDto,
    GetBotCommandsDto,
    SetBotProxyDto,
    UpdateAppearanceSettingsDto,
    UpdateBotCommandsDto,
    UpdateBotSettingsDto,
    UpdateOAuthSettingsDto,
    UpdateShopSettingsDto,
    UploadAppearanceImageDto,
)
from app.modules.settings.events import (
    BotSettingsChangedEvent,
    OidcIssuerChangedEvent,
    ShopSettingsChangedEvent,
)
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import (
    DeleteAppearanceLogoUseCase,
    GetBotCommandsUseCase,
    GetBotSettingsUseCase,
    GetBotStatusUseCase,
    GetOAuthSettingsUseCase,
    GetPublicAppearanceImageUseCase,
    GetPublicAppearanceUseCase,
    GetShopSettingsUseCase,
    RemoveBotProxyUseCase,
    ResetAppearanceSettingsUseCase,
    SetBotProxyUseCase,
    UpdateAppearanceSettingsUseCase,
    UpdateBotCommandsUseCase,
    UpdateBotSettingsUseCase,
    UpdateOAuthSettingsUseCase,
    UpdateShopSettingsUseCase,
    UploadAppearanceFaviconUseCase,
    UploadAppearanceLogoUseCase,
    get_bot_commands,
    update_bot_commands,
)
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import UserDto
from tests.fakes.events import RecordingEventPublisher
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot
from tests.modules.settings.factories import SHOP_SETTINGS_FIELDS, make_bot_commands_sync

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


@pytest.fixture(autouse=True)
async def _seed_actor_rows(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK, and the actor DTOs above have no rows
    for user_id in (1, 2):
        session.add(
            User(
                id=user_id,
                name=f"u{user_id}",
                telegram_id=user_id,
                role=Role.USER,
                language=Locale.EN,
                is_blocked=False,
            )
        )
    await session.flush()


async def _seed_en(translation_repository: TranslationRepository) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.seed_missing(Locale.EN, "command", "start", "Open the main menu")
    await translation_repository.seed_missing(Locale.EN, "command", "paysupport", "Refunds")
    await translation_repository.seed_missing(Locale.EN, "command", "terms", "Terms")


async def test_owner_can_view_and_update_bot_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    get_use_case = GetBotSettingsUseCase(settings_repository, uow)
    update_use_case = UpdateBotSettingsUseCase(settings_repository, uow, RecordingEventPublisher())

    settings = await get_use_case(OWNER)
    assert not settings.is_configured

    updated = await update_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )
    assert updated.is_configured


async def test_bot_status_is_unconfigured_without_a_token(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    status = await GetBotStatusUseCase(settings_repository, uow)(OWNER)

    assert status.is_configured is False
    assert status.is_running is False


async def test_bot_status_is_running_when_telegram_reports_a_webhook(
    settings_repository: SettingsRepository, uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    await UpdateBotSettingsUseCase(settings_repository, uow, RecordingEventPublisher())(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    async def _fake_fetch(token: str, proxy: Optional[str]) -> BotStatusDto:
        assert token == "123:abcdef"
        assert proxy is None
        return BotStatusDto(
            is_configured=True,
            webhook_url="https://bot.example.com/webhook",
            pending_update_count=2,
        )

    monkeypatch.setattr(
        "app.modules.settings.usecases.get_bot_status.fetch_bot_status", _fake_fetch
    )

    status = await GetBotStatusUseCase(settings_repository, uow)(OWNER)

    assert status.is_running is True
    assert status.pending_update_count == 2


async def test_set_bot_proxy_normalizes_socks5h_and_stores_it(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    settings = await SetBotProxyUseCase(settings_repository, uow, RecordingEventPublisher())(
        OWNER, SetBotProxyDto(proxy_url=" socks5h://user:pass@proxy.example:1080/ ")
    )

    assert settings.is_proxy_configured is True
    stored = await settings_repository.get_bot_settings()
    assert stored.proxy == "socks5://user:pass@proxy.example:1080"


@pytest.mark.parametrize(
    "proxy_url",
    [
        "socks4://proxy.example:1080",
        "https://proxy.example:443",
        "socks5://proxy.example",
        "proxy.example:1080",
        "http://:80",
    ],
)
async def test_set_bot_proxy_rejects_what_the_clients_cannot_use(
    settings_repository: SettingsRepository, uow: UnitOfWork, proxy_url: str
) -> None:
    with pytest.raises(ValidationError) as error:
        await SetBotProxyUseCase(settings_repository, uow, RecordingEventPublisher())(
            OWNER, SetBotProxyDto(proxy_url=proxy_url)
        )

    assert error.value.code == ErrorCode.BOT_PROXY_URL_INVALID
    assert (await settings_repository.get_bot_settings()).is_proxy_configured is False


async def test_remove_bot_proxy_clears_it(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await SetBotProxyUseCase(settings_repository, uow, RecordingEventPublisher())(
        OWNER, SetBotProxyDto(proxy_url="http://proxy.example:3128")
    )

    settings = await RemoveBotProxyUseCase(settings_repository, uow, RecordingEventPublisher())(
        OWNER
    )

    assert settings.is_proxy_configured is False
    assert (await settings_repository.get_bot_settings()).proxy is None


async def test_bot_status_goes_through_the_stored_proxy(
    settings_repository: SettingsRepository, uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    await UpdateBotSettingsUseCase(settings_repository, uow, RecordingEventPublisher())(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )
    await SetBotProxyUseCase(settings_repository, uow, RecordingEventPublisher())(
        OWNER, SetBotProxyDto(proxy_url="http://proxy.example:3128")
    )
    seen: list[Optional[str]] = []

    async def _fake_fetch(token: str, proxy: Optional[str]) -> BotStatusDto:
        seen.append(proxy)
        return BotStatusDto(is_configured=True)

    monkeypatch.setattr(
        "app.modules.settings.usecases.get_bot_status.fetch_bot_status", _fake_fetch
    )

    await GetBotStatusUseCase(settings_repository, uow)(OWNER)

    assert seen == ["http://proxy.example:3128"]


async def test_bot_status_is_not_running_while_telegram_reports_an_error(
    settings_repository: SettingsRepository, uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A configured token whose webhook Telegram cannot reach is exactly the
    # case the badge has to tell apart from "configured".
    await UpdateBotSettingsUseCase(settings_repository, uow, RecordingEventPublisher())(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    async def _failing_fetch(token: str, proxy: Optional[str]) -> BotStatusDto:
        return BotStatusDto(
            is_configured=True,
            webhook_url="https://bot.example.com/webhook",
            error="Connection refused",
        )

    monkeypatch.setattr(
        "app.modules.settings.usecases.get_bot_status.fetch_bot_status", _failing_fetch
    )

    status = await GetBotStatusUseCase(settings_repository, uow)(OWNER)

    assert status.is_configured is True
    assert status.is_running is False
    assert status.error == "Connection refused"


async def test_regular_user_cannot_view_bot_settings(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    get_use_case = GetBotSettingsUseCase(settings_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await get_use_case(REGULAR_USER)


async def test_regular_user_cannot_update_bot_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    update_use_case = UpdateBotSettingsUseCase(settings_repository, uow, RecordingEventPublisher())

    with pytest.raises(PermissionDeniedError):
        await update_use_case(REGULAR_USER, UpdateBotSettingsDto(token="123:abcdef"))


async def test_owner_can_view_and_update_shop_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    get_use_case = GetShopSettingsUseCase(settings_repository, uow)
    update_use_case = UpdateShopSettingsUseCase(settings_repository, uow, event_publisher)

    settings = await get_use_case(OWNER)
    assert settings.max_active_subscriptions == 3

    updated = await update_use_case(
        OWNER,
        UpdateShopSettingsDto(
            max_active_subscriptions=None,
            device_single_reset_enabled=True,
            device_single_reset_cooldown_hours=0,
            device_all_reset_enabled=True,
            device_all_reset_cooldown_hours=0,
            link_reset_enabled=True,
            link_reset_cooldown_hours=0,
            fields_set=SHOP_SETTINGS_FIELDS,
        ),
    )
    assert updated.max_active_subscriptions is None


async def test_regular_user_cannot_view_shop_settings(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    get_use_case = GetShopSettingsUseCase(settings_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await get_use_case(REGULAR_USER)


async def test_regular_user_cannot_update_shop_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    update_use_case = UpdateShopSettingsUseCase(settings_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await update_use_case(
            REGULAR_USER,
            UpdateShopSettingsDto(
                max_active_subscriptions=5,
                device_single_reset_enabled=True,
                device_single_reset_cooldown_hours=0,
                device_all_reset_enabled=True,
                device_all_reset_cooldown_hours=0,
                link_reset_enabled=True,
                link_reset_cooldown_hours=0,
                fields_set=SHOP_SETTINGS_FIELDS,
            ),
        )


async def test_update_shop_settings_rejects_non_positive_cap(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    update_use_case = UpdateShopSettingsUseCase(settings_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await update_use_case(
            OWNER,
            UpdateShopSettingsDto(
                max_active_subscriptions=0,
                device_single_reset_enabled=True,
                device_single_reset_cooldown_hours=0,
                device_all_reset_enabled=True,
                device_all_reset_cooldown_hours=0,
                link_reset_enabled=True,
                link_reset_cooldown_hours=0,
                fields_set=SHOP_SETTINGS_FIELDS,
            ),
        )


async def test_owner_can_view_and_update_oauth_settings(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    # assert_public_https_host resolves real DNS, stubbed here (the check
    # itself: test_update_oauth_settings_rejects_non_public_issuer_host)
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        "app.modules.settings.usecases.update_oauth_settings.assert_public_https_host",
        _fake_assert_public_https_host,
    )
    get_use_case = GetOAuthSettingsUseCase(settings_repository, uow)
    update_use_case = UpdateOAuthSettingsUseCase(
        settings_repository, uow, event_publisher, oauth_identity_repository
    )

    settings = await get_use_case(OWNER)
    assert not settings.is_github_configured
    assert not settings.is_oidc_configured

    updated = await update_use_case(
        OWNER,
        UpdateOAuthSettingsDto(
            github_client_id="gh-id",
            github_client_secret="gh-secret",
            oidc_issuer_url="https://keycloak.example.com/realms/myrealm",
            oidc_client_id="oidc-id",
            oidc_client_secret="oidc-secret",
            oidc_display_name="Keycloak",
        ),
    )
    assert updated.is_github_configured
    assert updated.is_oidc_configured
    assert updated.oidc_display_name == "Keycloak"


async def test_update_oauth_settings_rejects_non_public_issuer_host(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    update_use_case = UpdateOAuthSettingsUseCase(
        settings_repository, uow, event_publisher, oauth_identity_repository
    )

    with pytest.raises(ValidationError):
        await update_use_case(
            OWNER, UpdateOAuthSettingsDto(oidc_issuer_url="https://127.0.0.1/realms/myrealm")
        )


async def test_update_oauth_settings_publishes_oidc_issuer_changed_event_when_issuer_changes(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        "app.modules.settings.usecases.update_oauth_settings.assert_public_https_host",
        _fake_assert_public_https_host,
    )
    update_use_case = UpdateOAuthSettingsUseCase(
        settings_repository, uow, event_publisher, oauth_identity_repository
    )

    await update_use_case(
        OWNER, UpdateOAuthSettingsDto(oidc_issuer_url="https://keycloak.example.com/realms/first")
    )

    row = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == OidcIssuerChangedEvent.__name__
            )
        )
    ).one()
    assert row is not None


async def test_update_oauth_settings_does_not_publish_event_when_issuer_is_unchanged(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        "app.modules.settings.usecases.update_oauth_settings.assert_public_https_host",
        _fake_assert_public_https_host,
    )
    update_use_case = UpdateOAuthSettingsUseCase(
        settings_repository, uow, event_publisher, oauth_identity_repository
    )
    issuer_url = "https://keycloak.example.com/realms/stable"
    await update_use_case(OWNER, UpdateOAuthSettingsDto(oidc_issuer_url=issuer_url))
    # the first call published one OidcIssuerChangedEvent; the repeat must not

    await update_use_case(
        OWNER, UpdateOAuthSettingsDto(oidc_issuer_url=issuer_url, oidc_display_name="Renamed")
    )

    rows = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == OidcIssuerChangedEvent.__name__
            )
        )
    ).all()
    assert len(rows) == 1  # the second call added no event


async def _noop_async(url: str) -> None:
    return None


async def test_issuer_change_deletes_oidc_identities_in_same_transaction(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    monkeypatch.setattr(
        "app.modules.settings.usecases.update_oauth_settings.assert_public_https_host",
        _noop_async,
    )
    async with uow:
        await oauth_identity_repository.create(
            CreateOAuthIdentityDto(
                user_id=OWNER.id,
                provider=OAuthProvider.OIDC,
                external_id="sub-1",
                external_login=None,
            )
        )
        await oauth_identity_repository.create(
            CreateOAuthIdentityDto(
                user_id=OWNER.id,
                provider=OAuthProvider.GITHUB,
                external_id="gh-1",
                external_login=None,
            )
        )
    use_case = UpdateOAuthSettingsUseCase(
        settings_repository, uow, event_publisher, oauth_identity_repository
    )
    await use_case(OWNER, UpdateOAuthSettingsDto(oidc_issuer_url="https://idp-b.example.com"))

    async with uow:
        assert (
            await oauth_identity_repository.find_by_provider_external_id(
                OAuthProvider.OIDC, "sub-1"
            )
            is None
        )
        assert (
            await oauth_identity_repository.find_by_provider_external_id(
                OAuthProvider.GITHUB, "gh-1"
            )
            is not None
        )


async def test_same_issuer_keeps_oidc_identities(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    monkeypatch.setattr(
        "app.modules.settings.usecases.update_oauth_settings.assert_public_https_host",
        _noop_async,
    )
    use_case = UpdateOAuthSettingsUseCase(
        settings_repository, uow, event_publisher, oauth_identity_repository
    )
    issuer = "https://idp-a.example.com"
    await use_case(OWNER, UpdateOAuthSettingsDto(oidc_issuer_url=issuer))
    async with uow:
        await oauth_identity_repository.create(
            CreateOAuthIdentityDto(
                user_id=OWNER.id,
                provider=OAuthProvider.OIDC,
                external_id="sub-1",
                external_login=None,
            )
        )
    await use_case(OWNER, UpdateOAuthSettingsDto(oidc_issuer_url=issuer, oidc_display_name="X"))

    async with uow:
        assert (
            await oauth_identity_repository.find_by_provider_external_id(
                OAuthProvider.OIDC, "sub-1"
            )
            is not None
        )


async def test_regular_user_cannot_view_oauth_settings(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    get_use_case = GetOAuthSettingsUseCase(settings_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await get_use_case(REGULAR_USER)


async def test_owner_can_update_and_list_bot_commands(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )
    get_use_case = GetBotCommandsUseCase(settings_repository, uow)

    result = await update_use_case(
        OWNER,
        UpdateBotCommandsDto(commands=[("start", True), ("paysupport", True), ("terms", True)]),
    )

    assert [c.command for c in result.commands] == ["start", "paysupport", "terms"]
    assert result.telegram_sync_failed is False

    listed = await get_use_case(OWNER, GetBotCommandsDto())
    assert [c.command for c in listed] == ["start", "paysupport", "terms"]


async def test_get_bot_commands_defaults_to_current_registry_when_db_is_empty(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    get_use_case = GetBotCommandsUseCase(settings_repository, uow)

    listed = await get_use_case(OWNER, GetBotCommandsDto())

    assert [c.command for c in listed] == ["start", "paysupport", "terms"]
    assert listed[0].enabled is True


async def test_get_bot_commands_with_default_order_ignores_the_stored_order(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    await settings_repository.replace_bot_commands([("start", False)])
    get_use_case = GetBotCommandsUseCase(settings_repository, uow)

    listed = await get_use_case(OWNER, GetBotCommandsDto(default_order=True))

    assert [c.command for c in listed] == [c.command for c in BOT_COMMANDS]
    assert listed[0].enabled is False


async def test_update_bot_commands_rejects_unknown_command(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await update_use_case(
            OWNER, UpdateBotCommandsDto(commands=[("start", True), ("help", True)])
        )


async def test_update_bot_commands_rejects_missing_command(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await update_use_case(OWNER, UpdateBotCommandsDto(commands=[]))


async def test_get_bot_commands_drops_stale_rows_not_in_registry(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    await settings_repository.replace_bot_commands([("ghost", True)])
    get_use_case = GetBotCommandsUseCase(settings_repository, uow)

    listed = await get_use_case(OWNER, GetBotCommandsDto())

    assert [c.command for c in listed] == ["start", "paysupport", "terms"]


async def test_regular_user_cannot_view_bot_commands(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    get_use_case = GetBotCommandsUseCase(settings_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await get_use_case(REGULAR_USER)


async def test_regular_user_cannot_update_bot_commands(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    with pytest.raises(PermissionDeniedError):
        await update_use_case(
            REGULAR_USER, [("start", True), ("paysupport", True), ("terms", True)]
        )


async def test_update_bot_commands_does_not_push_to_telegram_when_bot_unconfigured(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    result = await update_use_case(
        OWNER,
        UpdateBotCommandsDto(commands=[("start", True), ("paysupport", True), ("terms", True)]),
    )

    assert result.telegram_sync_failed is False


def _capture_command_pushes(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    pushed: list[dict] = []

    def _set(method: SetMyCommands) -> bool:
        pushed.append(method.model_dump(mode="json", exclude_none=True))
        return True

    use_fake_bot(monkeypatch, FakeBotSession({"SetMyCommands": _set, "DeleteMyCommands": True}))
    return pushed


async def test_update_bot_commands_pushes_once_per_locale_plus_default(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await _seed_en(translation_repository)
    await translation_repository.add_active_locale(Locale.RU)
    await translation_repository.seed_missing(Locale.RU, "command", "start", "Открыть главное меню")
    await translation_repository.seed_missing(Locale.RU, "command", "paysupport", "Возврат")
    await translation_repository.seed_missing(Locale.RU, "command", "terms", "Документы")

    settings_use_case = UpdateBotSettingsUseCase(
        settings_repository, uow, RecordingEventPublisher()
    )
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    pushed = _capture_command_pushes(monkeypatch)

    result = await update_use_case(
        OWNER,
        UpdateBotCommandsDto(commands=[("start", True), ("paysupport", True), ("terms", True)]),
    )

    assert result.telegram_sync_failed is False
    active_locales = await translation_repository.list_active_locales()
    expected_language_codes = [locale.value for locale in active_locales] + [None]
    assert [p.get("language_code") for p in pushed] == expected_language_codes
    for payload in pushed:
        assert [c["command"] for c in payload["commands"]] == ["start", "paysupport", "terms"]
        assert payload["scope"] == {"type": "all_private_chats"}


async def test_update_bot_commands_resolves_distinct_text_per_locale(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.add_active_locale(Locale.RU)
    await translation_repository.seed_missing(Locale.EN, "command", "start", "Open the main menu")
    await translation_repository.seed_missing(Locale.EN, "command", "paysupport", "Refunds")
    await translation_repository.seed_missing(Locale.EN, "command", "terms", "Terms")
    await translation_repository.seed_missing(Locale.RU, "command", "start", "Открыть главное меню")
    await translation_repository.seed_missing(Locale.RU, "command", "paysupport", "Возврат")
    await translation_repository.seed_missing(Locale.RU, "command", "terms", "Документы")

    settings_use_case = UpdateBotSettingsUseCase(
        settings_repository, uow, RecordingEventPublisher()
    )
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    pushed = _capture_command_pushes(monkeypatch)

    result = await update_use_case(
        OWNER,
        UpdateBotCommandsDto(commands=[("start", True), ("paysupport", True), ("terms", True)]),
    )

    assert result.telegram_sync_failed is False
    assert [p.get("language_code") for p in pushed] == ["en", "ru", None]
    texts = {p.get("language_code"): p["commands"][0]["description"] for p in pushed}
    assert texts["en"] == "Open the main menu"
    assert texts["ru"] == "Открыть главное меню"


async def test_update_bot_commands_reports_sync_failure_when_locale_file_missing(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await _seed_en(translation_repository)
    await translation_repository.add_active_locale(Locale.RU)
    # an active `ru` locale with no row for the key

    settings_use_case = UpdateBotSettingsUseCase(
        settings_repository, uow, RecordingEventPublisher()
    )
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    result = await update_use_case(
        OWNER,
        UpdateBotCommandsDto(commands=[("start", True), ("paysupport", True), ("terms", True)]),
    )

    assert result.telegram_sync_failed is True


async def test_update_bot_commands_excludes_disabled_from_telegram_push(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await _seed_en(translation_repository)
    await translation_repository.add_active_locale(Locale.RU)
    await translation_repository.seed_missing(Locale.RU, "command", "start", "Открыть главное меню")
    await translation_repository.seed_missing(Locale.RU, "command", "paysupport", "Возврат")
    await translation_repository.seed_missing(Locale.RU, "command", "terms", "Документы")

    commands = (
        BotCommand(command="start", description_key="command.start"),
        BotCommand(command="help", description_key="command.missing"),
    )
    for module in (update_bot_commands, get_bot_commands, command_translations):
        monkeypatch.setattr(module, "BOT_COMMANDS", commands)

    settings_use_case = UpdateBotSettingsUseCase(
        settings_repository, uow, RecordingEventPublisher()
    )
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    pushed = _capture_command_pushes(monkeypatch)

    # "help" is disabled, so its missing description_key is never looked up
    result = await update_use_case(
        OWNER, UpdateBotCommandsDto(commands=[("start", True), ("help", False)])
    )

    assert result.telegram_sync_failed is False
    for payload in pushed:
        assert [c["command"] for c in payload["commands"]] == ["start"]


async def test_update_bot_commands_reports_telegram_sync_failure_on_missing_translation(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    monkeypatch.setattr(
        update_bot_commands,
        "BOT_COMMANDS",
        (BotCommand(command="start", description_key="command.missing"),),
    )

    settings_use_case = UpdateBotSettingsUseCase(
        settings_repository, uow, RecordingEventPublisher()
    )
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    result = await update_use_case(OWNER, UpdateBotCommandsDto(commands=[("start", True)]))

    assert result.telegram_sync_failed is True


async def test_update_bot_commands_reports_telegram_sync_success(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    settings_use_case = UpdateBotSettingsUseCase(
        settings_repository, uow, RecordingEventPublisher()
    )
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RecordingEventPublisher(),
    )

    await _seed_en(translation_repository)
    _capture_command_pushes(monkeypatch)

    result = await update_use_case(
        OWNER,
        UpdateBotCommandsDto(commands=[("start", True), ("paysupport", True), ("terms", True)]),
    )

    assert result.telegram_sync_failed is False


async def test_admin_with_only_bot_commands_permission_cannot_update_bot_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    update_use_case = UpdateBotSettingsUseCase(settings_repository, uow, RecordingEventPublisher())
    limited_admin = UserDto(
        id=99,
        login="limited",
        name="limited",
        role=Role.ADMIN,
        language=Locale.EN,
        permission_grants=[Permission.BOT_COMMANDS_MANAGE.value],
        permission_revokes=[Permission.BOT_SETTINGS_MANAGE.value],
    )

    with pytest.raises(PermissionDeniedError):
        await update_use_case(limited_admin, UpdateBotSettingsDto(token="123:abcdef"))


def _png(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height)).save(buffer, format="PNG")
    return buffer.getvalue()


# Real PNG bytes so uploads exercise the magic-byte and dimension checks.
FAKE_PNG_APPEARANCE: bytes = _png(128, 128)


def _appearance_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


async def test_get_public_appearance_returns_defaults(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    use_case = GetPublicAppearanceUseCase(settings_repository, uow)

    settings = await use_case.execute(AppearanceTarget.DASHBOARD)

    assert settings.brand_name is None
    assert settings.has_logo is False


async def test_owner_can_update_appearance_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    use_case = UpdateAppearanceSettingsUseCase(settings_repository, uow, RecordingEventPublisher())

    settings = await use_case(
        OWNER,
        UpdateAppearanceSettingsDto(
            target=AppearanceTarget.DASHBOARD,
            brand_name="Acme VPN",
            primary_color="#22d3ee",
            shader_palette=["#111111", "#222222", "#333333", "#444444"],
            shader_enabled=False,
        ),
    )

    assert settings.brand_name == "Acme VPN"
    assert settings.primary_color == "#22d3ee"
    assert settings.shader_palette == ["#111111", "#222222", "#333333", "#444444"]
    assert settings.shader_enabled is False


async def test_cabinet_appearance_is_separate_from_dashboard(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    publisher = RecordingEventPublisher()
    use_case = UpdateAppearanceSettingsUseCase(settings_repository, uow, publisher)

    await use_case(
        OWNER,
        UpdateAppearanceSettingsDto(target=AppearanceTarget.CABINET, brand_name="Acme Cabinet"),
    )

    get_use_case = GetPublicAppearanceUseCase(settings_repository, uow)
    assert (await get_use_case.execute(AppearanceTarget.CABINET)).brand_name == "Acme Cabinet"
    assert (await get_use_case.execute(AppearanceTarget.DASHBOARD)).brand_name is None
    event = publisher.events[-1]
    assert event.target == AppearanceTarget.CABINET
    assert event.changed_fields == ["brand_name"]


async def test_regular_user_cannot_update_appearance_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    use_case = UpdateAppearanceSettingsUseCase(settings_repository, uow, RecordingEventPublisher())

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdateAppearanceSettingsDto(target=AppearanceTarget.DASHBOARD, brand_name="Acme VPN"),
        )


async def test_owner_can_reset_appearance_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    update_use_case = UpdateAppearanceSettingsUseCase(
        settings_repository, uow, RecordingEventPublisher()
    )
    reset_use_case = ResetAppearanceSettingsUseCase(
        settings_repository, uow, RecordingEventPublisher()
    )

    await update_use_case(
        OWNER,
        UpdateAppearanceSettingsDto(
            target=AppearanceTarget.DASHBOARD,
            brand_name="Acme VPN",
            primary_color="#22d3ee",
            shader_palette=["#111111", "#222222", "#333333", "#444444"],
            shader_enabled=False,
        ),
    )
    settings = await reset_use_case(OWNER, AppearanceTarget.DASHBOARD)

    assert settings.brand_name is None
    assert settings.primary_color is None
    assert settings.shader_palette is None
    assert settings.shader_enabled is True


async def test_regular_user_cannot_reset_appearance_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    use_case = ResetAppearanceSettingsUseCase(settings_repository, uow, RecordingEventPublisher())

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, AppearanceTarget.DASHBOARD)


async def test_owner_can_upload_and_fetch_logo(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    upload_use_case = UploadAppearanceLogoUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    get_use_case = GetPublicAppearanceImageUseCase(settings_repository, cfg, uow)

    settings = await upload_use_case(
        OWNER,
        UploadAppearanceImageDto(
            target=AppearanceTarget.DASHBOARD, content_type="image/png", data=FAKE_PNG_APPEARANCE
        ),
    )
    assert settings.has_logo is True

    image = await get_use_case.execute(AppearanceTarget.DASHBOARD, AppearanceImageKind.LOGO)
    data, content_type = image.data, image.content_type
    assert data == FAKE_PNG_APPEARANCE
    assert content_type == "image/png"


_SVG_NS: str = "xmlns='http://www.w3.org/2000/svg'"


async def test_upload_accepts_plain_square_svg(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    logo_use_case = UploadAppearanceLogoUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    svg_data = f"<svg {_SVG_NS} viewBox='0 0 64 64'><rect width='64' height='64'/></svg>".encode()

    settings = await logo_use_case(
        OWNER,
        UploadAppearanceImageDto(
            target=AppearanceTarget.DASHBOARD, content_type="image/svg+xml", data=svg_data
        ),
    )

    assert settings.has_logo is True
    assert (tmp_path / "appearance" / "logo.svg").read_bytes() == svg_data


@pytest.mark.parametrize(
    "svg",
    [
        f"<svg {_SVG_NS} viewBox='0 0 64 32'></svg>",
        f"<svg {_SVG_NS}></svg>",
        f"<svg {_SVG_NS} viewBox='0 0 64 64'><script>alert(1)</script></svg>",
        f"<svg {_SVG_NS} viewBox='0 0 64 64' onload='alert(1)'></svg>",
        f"<svg {_SVG_NS} viewBox='0 0 64 64'><a href='javascript:alert(1)'><rect/></a></svg>",
        f"<svg {_SVG_NS} viewBox='0 0 64 64'><foreignObject></foreignObject></svg>",
        f"<!DOCTYPE svg [<!ENTITY a 'x'>]><svg {_SVG_NS} viewBox='0 0 64 64'>&a;</svg>",
        "<html><body></body></html>",
        "not xml at all",
    ],
)
async def test_upload_rejects_unsafe_or_invalid_svg(
    settings_repository: SettingsRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
    svg: str,
) -> None:
    use_case = UploadAppearanceFaviconUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow, RecordingEventPublisher()
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadAppearanceImageDto(
                target=AppearanceTarget.DASHBOARD, content_type="image/svg+xml", data=svg.encode()
            ),
        )


async def test_upload_rejects_unsupported_content_type(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    use_case = UploadAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow, RecordingEventPublisher()
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadAppearanceImageDto(
                target=AppearanceTarget.DASHBOARD, content_type="application/pdf", data=b"x"
            ),
        )


async def test_upload_rejects_content_not_matching_declared_type(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    use_case = UploadAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow, RecordingEventPublisher()
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadAppearanceImageDto(
                target=AppearanceTarget.DASHBOARD,
                content_type="image/png",
                data=b"this is not actually a png",
            ),
        )


async def test_upload_rejects_oversized_file(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    use_case = UploadAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow, RecordingEventPublisher()
    )
    oversized = FAKE_PNG_APPEARANCE + b"x" * (1024 * 1024 + 1)

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadAppearanceImageDto(
                target=AppearanceTarget.DASHBOARD, content_type="image/png", data=oversized
            ),
        )


async def test_upload_favicon_has_its_own_weight_limit(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    use_case = UploadAppearanceFaviconUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow, RecordingEventPublisher()
    )
    oversized = _png(32, 32) + b"x" * (256 * 1024 + 1)

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadAppearanceImageDto(
                target=AppearanceTarget.DASHBOARD, content_type="image/png", data=oversized
            ),
        )


@pytest.mark.parametrize(("width", "height"), [(128, 64), (64, 64), (2048, 2048)])
async def test_upload_logo_rejects_bad_dimensions(
    settings_repository: SettingsRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
    width: int,
    height: int,
) -> None:
    use_case = UploadAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow, RecordingEventPublisher()
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadAppearanceImageDto(
                target=AppearanceTarget.DASHBOARD,
                content_type="image/png",
                data=_png(width, height),
            ),
        )


async def test_upload_favicon_accepts_small_square(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    use_case = UploadAppearanceFaviconUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow, RecordingEventPublisher()
    )

    settings = await use_case(
        OWNER,
        UploadAppearanceImageDto(
            target=AppearanceTarget.DASHBOARD, content_type="image/png", data=_png(32, 32)
        ),
    )

    assert settings.has_favicon is True


async def test_get_appearance_image_missing_raises_not_found(
    settings_repository: SettingsRepository,
    config: AppConfig,
    tmp_path: Path,
    uow: UnitOfWork,
) -> None:
    use_case = GetPublicAppearanceImageUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow
    )

    with pytest.raises(NotFoundError):
        await use_case.execute(AppearanceTarget.DASHBOARD, AppearanceImageKind.LOGO)


async def test_owner_can_delete_uploaded_logo(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    upload_use_case = UploadAppearanceLogoUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    delete_use_case = DeleteAppearanceLogoUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )

    await upload_use_case(
        OWNER,
        UploadAppearanceImageDto(
            target=AppearanceTarget.DASHBOARD, content_type="image/png", data=FAKE_PNG_APPEARANCE
        ),
    )
    settings = await delete_use_case(OWNER, AppearanceTarget.DASHBOARD)

    assert settings.has_logo is False
    assert not (tmp_path / "appearance" / "logo.png").exists()


async def test_delete_missing_appearance_image_raises_not_found(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    delete_use_case = DeleteAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow, RecordingEventPublisher()
    )

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, AppearanceTarget.DASHBOARD)


async def test_admin_with_only_logo_permission_cannot_upload_favicon(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    logo_use_case = UploadAppearanceLogoUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    favicon_use_case = UploadAppearanceFaviconUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    limited_admin = UserDto(
        id=100,
        login="logo-admin",
        name="logo-admin",
        role=Role.ADMIN,
        language=Locale.EN,
        permission_grants=[Permission.APPEARANCE_LOGO_UPLOAD.value],
    )

    settings = await logo_use_case(
        limited_admin,
        UploadAppearanceImageDto(
            target=AppearanceTarget.DASHBOARD, content_type="image/png", data=FAKE_PNG_APPEARANCE
        ),
    )
    assert settings.has_logo is True

    with pytest.raises(PermissionDeniedError):
        await favicon_use_case(
            limited_admin,
            UploadAppearanceImageDto(
                target=AppearanceTarget.DASHBOARD,
                content_type="image/png",
                data=FAKE_PNG_APPEARANCE,
            ),
        )


async def test_admin_with_upload_permission_cannot_delete(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    upload_use_case = UploadAppearanceLogoUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    delete_use_case = DeleteAppearanceLogoUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    upload_only_admin = UserDto(
        id=102,
        login="upload-only-admin",
        name="upload-only-admin",
        role=Role.ADMIN,
        language=Locale.EN,
        permission_grants=[Permission.APPEARANCE_LOGO_UPLOAD.value],
    )

    await upload_use_case(
        upload_only_admin,
        UploadAppearanceImageDto(
            target=AppearanceTarget.DASHBOARD, content_type="image/png", data=FAKE_PNG_APPEARANCE
        ),
    )

    with pytest.raises(PermissionDeniedError):
        await delete_use_case(upload_only_admin, AppearanceTarget.DASHBOARD)


async def test_admin_with_only_favicon_permission_cannot_upload_logo(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    logo_use_case = UploadAppearanceLogoUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    favicon_use_case = UploadAppearanceFaviconUseCase(
        settings_repository, cfg, uow, RecordingEventPublisher()
    )
    limited_admin = UserDto(
        id=101,
        login="favicon-admin",
        name="favicon-admin",
        role=Role.ADMIN,
        language=Locale.EN,
        permission_grants=[Permission.APPEARANCE_FAVICON_UPLOAD.value],
    )

    settings = await favicon_use_case(
        limited_admin,
        UploadAppearanceImageDto(
            target=AppearanceTarget.DASHBOARD, content_type="image/png", data=FAKE_PNG_APPEARANCE
        ),
    )
    assert settings.has_favicon is True

    with pytest.raises(PermissionDeniedError):
        await logo_use_case(
            limited_admin,
            UploadAppearanceImageDto(
                target=AppearanceTarget.DASHBOARD,
                content_type="image/png",
                data=FAKE_PNG_APPEARANCE,
            ),
        )


async def test_shop_settings_patch_keeps_unsent_fields(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    update_use_case = UpdateShopSettingsUseCase(settings_repository, uow, event_publisher)
    await update_use_case(
        OWNER,
        UpdateShopSettingsDto(
            max_active_subscriptions=3,
            link_reset_cooldown_hours=24,
            fields_set=frozenset({"max_active_subscriptions", "link_reset_cooldown_hours"}),
        ),
    )

    updated = await update_use_case(
        OWNER,
        UpdateShopSettingsDto(
            link_reset_enabled=False, fields_set=frozenset({"link_reset_enabled"})
        ),
    )

    assert updated.max_active_subscriptions == 3
    assert updated.link_reset_cooldown_hours == 24
    assert updated.link_reset_enabled is False
    events = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == ShopSettingsChangedEvent.__name__
            )
        )
    ).all()
    assert len(events) == 2


async def test_shop_settings_patch_sets_unlimited_when_null_is_sent(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    update_use_case = UpdateShopSettingsUseCase(settings_repository, uow, event_publisher)

    updated = await update_use_case(
        OWNER,
        UpdateShopSettingsDto(
            max_active_subscriptions=None, fields_set=frozenset({"max_active_subscriptions"})
        ),
    )

    assert updated.max_active_subscriptions is None
    assert updated.device_single_reset_enabled is True


async def test_bot_token_change_is_audited_without_its_value(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    publisher = RecordingEventPublisher()

    await UpdateBotSettingsUseCase(settings_repository, uow, publisher)(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    [event] = publisher.events
    assert isinstance(event, BotSettingsChangedEvent)
    assert event.changed_fields == ["secret_token", "token"]
    assert "123:abcdef" not in repr(event)
