from pathlib import Path
from typing import Optional

import pytest
from aiogram import Bot
from aiogram.methods.set_my_commands import SetMyCommands
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageKind, Locale, Role
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.modules.settings.bot_commands import BotCommand
from app.modules.settings.dto import (
    UpdateAppearanceSettingsDto,
    UpdateBotSettingsDto,
    UpdateOAuthSettingsDto,
    UpdateShopSettingsDto,
)
from app.modules.settings.events import LocaleActivatedEvent, LocaleDeactivatedEvent
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import (
    AddLocaleUseCase,
    DeleteAppearanceLogoUseCase,
    GetBotCommandsUseCase,
    GetBotSettingsUseCase,
    GetOAuthSettingsUseCase,
    GetPublicAppearanceImageUseCase,
    GetPublicAppearanceUseCase,
    GetShopSettingsUseCase,
    ListActiveLocalesUseCase,
    RemoveLocaleUseCase,
    ResetAppearanceSettingsUseCase,
    UpdateAppearanceSettingsUseCase,
    UpdateBotCommandsUseCase,
    UpdateBotSettingsUseCase,
    UpdateOAuthSettingsUseCase,
    UpdateShopSettingsUseCase,
    UploadAppearanceFaviconUseCase,
    UploadAppearanceImageInput,
    UploadAppearanceLogoUseCase,
    update_bot_commands,
)
from app.modules.translations.repository import TranslationsRepository
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def _seed_en(
    settings_repository: SettingsRepository, translations_repository: TranslationsRepository
) -> None:
    await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")


async def test_owner_can_view_and_update_bot_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    get_use_case = GetBotSettingsUseCase(settings_repository)
    update_use_case = UpdateBotSettingsUseCase(settings_repository, uow)

    settings = await get_use_case(OWNER)
    assert not settings.is_configured

    updated = await update_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )
    assert updated.is_configured


async def test_regular_user_cannot_view_bot_settings(
    settings_repository: SettingsRepository,
) -> None:
    get_use_case = GetBotSettingsUseCase(settings_repository)

    with pytest.raises(PermissionDeniedError):
        await get_use_case(REGULAR_USER)


async def test_regular_user_cannot_update_bot_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    update_use_case = UpdateBotSettingsUseCase(settings_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await update_use_case(REGULAR_USER, UpdateBotSettingsDto(token="123:abcdef"))


async def test_owner_can_view_and_update_shop_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    get_use_case = GetShopSettingsUseCase(settings_repository)
    update_use_case = UpdateShopSettingsUseCase(settings_repository, uow)

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
        ),
    )
    assert updated.max_active_subscriptions is None


async def test_regular_user_cannot_view_shop_settings(
    settings_repository: SettingsRepository,
) -> None:
    get_use_case = GetShopSettingsUseCase(settings_repository)

    with pytest.raises(PermissionDeniedError):
        await get_use_case(REGULAR_USER)


async def test_regular_user_cannot_update_shop_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    update_use_case = UpdateShopSettingsUseCase(settings_repository, uow)

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
            ),
        )


async def test_update_shop_settings_rejects_non_positive_cap(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    update_use_case = UpdateShopSettingsUseCase(settings_repository, uow)

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
            ),
        )


async def test_owner_can_view_and_update_oauth_settings(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
    event_publisher: EventPublisher,
) -> None:
    # oidc_issuer_url goes through assert_public_https_host's real DNS
    # resolution (see test_update_oauth_settings_rejects_non_public_issuer_host
    # for that check itself) -- stubbed here since this test is about the
    # write path, not network-dependent hostname resolution.
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        "app.modules.settings.usecases.update_oauth_settings.assert_public_https_host",
        _fake_assert_public_https_host,
    )
    get_use_case = GetOAuthSettingsUseCase(settings_repository)
    update_use_case = UpdateOAuthSettingsUseCase(settings_repository, uow, event_publisher)

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
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    update_use_case = UpdateOAuthSettingsUseCase(settings_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await update_use_case(
            OWNER, UpdateOAuthSettingsDto(oidc_issuer_url="https://127.0.0.1/realms/myrealm")
        )


async def test_regular_user_cannot_view_oauth_settings(
    settings_repository: SettingsRepository,
) -> None:
    get_use_case = GetOAuthSettingsUseCase(settings_repository)

    with pytest.raises(PermissionDeniedError):
        await get_use_case(REGULAR_USER)


async def test_owner_can_update_and_list_bot_commands(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )
    get_use_case = GetBotCommandsUseCase(settings_repository)

    result = await update_use_case(OWNER, [("menu", True)])

    assert [c.command for c in result.commands] == ["menu"]
    assert result.telegram_sync_failed is False

    listed = await get_use_case(OWNER)
    assert [c.command for c in listed] == ["menu"]


async def test_get_bot_commands_defaults_to_current_registry_when_db_is_empty(
    settings_repository: SettingsRepository,
) -> None:
    get_use_case = GetBotCommandsUseCase(settings_repository)

    listed = await get_use_case(OWNER)

    assert [c.command for c in listed] == ["menu"]
    assert listed[0].enabled is True


async def test_update_bot_commands_rejects_unknown_command(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    with pytest.raises(ValidationError):
        await update_use_case(OWNER, [("menu", True), ("help", True)])


async def test_update_bot_commands_rejects_missing_command(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    with pytest.raises(ValidationError):
        await update_use_case(OWNER, [])


async def test_get_bot_commands_drops_stale_rows_not_in_registry(
    settings_repository: SettingsRepository,
) -> None:
    # Bypasses the usecase's validation on purpose -- simulates a command left
    # over from before a handler was removed from the registry.
    await settings_repository.replace_bot_commands([("ghost", True)])
    get_use_case = GetBotCommandsUseCase(settings_repository)

    listed = await get_use_case(OWNER)

    assert [c.command for c in listed] == ["menu"]


async def test_regular_user_cannot_view_bot_commands(
    settings_repository: SettingsRepository,
) -> None:
    get_use_case = GetBotCommandsUseCase(settings_repository)

    with pytest.raises(PermissionDeniedError):
        await get_use_case(REGULAR_USER)


async def test_regular_user_cannot_update_bot_commands(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    with pytest.raises(PermissionDeniedError):
        await update_use_case(REGULAR_USER, [("menu", True)])


async def test_update_bot_commands_does_not_push_to_telegram_when_bot_unconfigured(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    result = await update_use_case(OWNER, [("menu", True)])

    assert result.telegram_sync_failed is False


async def test_update_bot_commands_pushes_once_per_locale_plus_default(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    await _seed_en(settings_repository, translations_repository)
    await settings_repository.add_active_locale(Locale.RU)
    await translations_repository.seed_missing(Locale.RU, "command", "menu", "Открыть главное меню")

    settings_use_case = UpdateBotSettingsUseCase(settings_repository, uow)
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    pushed: list[SetMyCommands] = []

    async def _capturing_call(self: Bot, method: SetMyCommands, request_timeout=None):  # type: ignore[no-untyped-def]
        pushed.append(method)
        return True

    monkeypatch.setattr(Bot, "__call__", _capturing_call)

    result = await update_use_case(OWNER, [("menu", True)])

    assert result.telegram_sync_failed is False
    active_locales = await settings_repository.list_active_locales()
    expected_language_codes = [locale.value for locale in active_locales] + [None]
    assert [p.language_code for p in pushed] == expected_language_codes
    for method in pushed:
        assert [c.command for c in method.commands] == ["menu"]


async def test_update_bot_commands_resolves_distinct_text_per_locale(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    await settings_repository.add_active_locale(Locale.EN)
    await settings_repository.add_active_locale(Locale.RU)
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")
    await translations_repository.seed_missing(Locale.RU, "command", "menu", "Открыть главное меню")

    settings_use_case = UpdateBotSettingsUseCase(settings_repository, uow)
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    pushed: list[SetMyCommands] = []

    async def _capturing_call(self: Bot, method: SetMyCommands, request_timeout=None):  # type: ignore[no-untyped-def]
        pushed.append(method)
        return True

    monkeypatch.setattr(Bot, "__call__", _capturing_call)

    result = await update_use_case(OWNER, [("menu", True)])

    assert result.telegram_sync_failed is False
    assert [p.language_code for p in pushed] == ["en", "ru", None]
    texts = {p.language_code: p.commands[0].description for p in pushed}
    assert texts["en"] == "Open the main menu"
    assert texts["ru"] == "Открыть главное меню"


async def test_update_bot_commands_reports_sync_failure_when_locale_file_missing(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    await _seed_en(settings_repository, translations_repository)
    await settings_repository.add_active_locale(Locale.RU)
    # No `ru` translation seeded at all -- an active locale with no row for the key.

    settings_use_case = UpdateBotSettingsUseCase(settings_repository, uow)
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    result = await update_use_case(OWNER, [("menu", True)])

    assert result.telegram_sync_failed is True


async def test_update_bot_commands_excludes_disabled_from_telegram_push(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    await _seed_en(settings_repository, translations_repository)
    await settings_repository.add_active_locale(Locale.RU)
    await translations_repository.seed_missing(Locale.RU, "command", "menu", "Открыть главное меню")

    monkeypatch.setattr(
        update_bot_commands,
        "BOT_COMMANDS",
        (
            BotCommand(command="menu", description_key="command.menu"),
            BotCommand(command="help", description_key="command.missing"),
        ),
    )

    settings_use_case = UpdateBotSettingsUseCase(settings_repository, uow)
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    pushed: list[SetMyCommands] = []

    async def _capturing_call(self: Bot, method: SetMyCommands, request_timeout=None):  # type: ignore[no-untyped-def]
        pushed.append(method)
        return True

    monkeypatch.setattr(Bot, "__call__", _capturing_call)

    # "help" is disabled, so its unresolved description_key ("command.missing")
    # never gets looked up -- only "menu" (enabled) is pushed.
    result = await update_use_case(OWNER, [("menu", True), ("help", False)])

    assert result.telegram_sync_failed is False
    for method in pushed:
        assert [c.command for c in method.commands] == ["menu"]


async def test_update_bot_commands_reports_telegram_sync_failure_on_missing_translation(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    monkeypatch.setattr(
        update_bot_commands,
        "BOT_COMMANDS",
        (BotCommand(command="menu", description_key="command.missing"),),
    )

    settings_use_case = UpdateBotSettingsUseCase(settings_repository, uow)
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    result = await update_use_case(OWNER, [("menu", True)])

    assert result.telegram_sync_failed is True


async def test_update_bot_commands_reports_telegram_sync_success(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    settings_use_case = UpdateBotSettingsUseCase(settings_repository, uow)
    await settings_use_case(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    update_use_case = UpdateBotCommandsUseCase(
        settings_repository, translations_repository, uow, config
    )

    async def _succeeding_push(token: Optional[str], commands: list) -> bool:
        return True

    monkeypatch.setattr(update_use_case, "_push_to_telegram", _succeeding_push)

    result = await update_use_case(OWNER, [("menu", True)])

    assert result.telegram_sync_failed is False


async def test_owner_can_add_and_list_active_locales(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    add_use_case = AddLocaleUseCase(settings_repository, uow, event_publisher)
    list_use_case = ListActiveLocalesUseCase(settings_repository)

    await add_use_case(OWNER, Locale.RU)

    assert set(await list_use_case(OWNER)) == {Locale.RU}


async def test_add_locale_publishes_locale_activated_event(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    event_publisher: EventPublisher,
) -> None:
    add_use_case = AddLocaleUseCase(settings_repository, uow, event_publisher)

    await add_use_case(OWNER, Locale.RU)

    row = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == LocaleActivatedEvent.__name__
            )
        )
    ).one()
    assert row.payload["locale"] == Locale.RU


async def test_add_locale_rejects_duplicate(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    add_use_case = AddLocaleUseCase(settings_repository, uow, event_publisher)
    await add_use_case(OWNER, Locale.RU)

    with pytest.raises(ConflictError):
        await add_use_case(OWNER, Locale.RU)


async def test_remove_locale_publishes_locale_deactivated_event(
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    event_publisher: EventPublisher,
) -> None:
    add_use_case = AddLocaleUseCase(settings_repository, uow, event_publisher)
    remove_use_case = RemoveLocaleUseCase(settings_repository, uow, event_publisher)
    await add_use_case(OWNER, Locale.RU)

    await remove_use_case(OWNER, Locale.RU)

    row = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == LocaleDeactivatedEvent.__name__
            )
        )
    ).one()
    assert row.payload["locale"] == Locale.RU


async def test_remove_locale_rejects_en(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    remove_use_case = RemoveLocaleUseCase(settings_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await remove_use_case(OWNER, Locale.EN)


async def test_regular_user_cannot_add_locale(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    add_use_case = AddLocaleUseCase(settings_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await add_use_case(REGULAR_USER, Locale.RU)


async def test_admin_with_only_bot_commands_permission_cannot_update_bot_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    update_use_case = UpdateBotSettingsUseCase(settings_repository, uow)
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


# Real PNG bytes so uploads exercise the actual magic-byte check.
FAKE_PNG_APPEARANCE: bytes = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"


def _appearance_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


async def test_get_public_appearance_returns_defaults(
    settings_repository: SettingsRepository,
) -> None:
    use_case = GetPublicAppearanceUseCase(settings_repository)

    settings = await use_case.execute()

    assert settings.brand_name is None
    assert settings.has_logo is False


async def test_owner_can_update_appearance_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    use_case = UpdateAppearanceSettingsUseCase(settings_repository, uow)

    settings = await use_case(
        OWNER,
        UpdateAppearanceSettingsDto(
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


async def test_regular_user_cannot_update_appearance_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    use_case = UpdateAppearanceSettingsUseCase(settings_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, UpdateAppearanceSettingsDto(brand_name="Acme VPN"))


async def test_owner_can_reset_appearance_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    update_use_case = UpdateAppearanceSettingsUseCase(settings_repository, uow)
    reset_use_case = ResetAppearanceSettingsUseCase(settings_repository, uow)

    await update_use_case(
        OWNER,
        UpdateAppearanceSettingsDto(
            brand_name="Acme VPN",
            primary_color="#22d3ee",
            shader_palette=["#111111", "#222222", "#333333", "#444444"],
            shader_enabled=False,
        ),
    )
    settings = await reset_use_case(OWNER)

    assert settings.brand_name is None
    assert settings.primary_color is None
    assert settings.shader_palette is None
    assert settings.shader_enabled is True


async def test_regular_user_cannot_reset_appearance_settings(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    use_case = ResetAppearanceSettingsUseCase(settings_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER)


async def test_owner_can_upload_and_fetch_logo(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    upload_use_case = UploadAppearanceLogoUseCase(settings_repository, cfg, uow)
    get_use_case = GetPublicAppearanceImageUseCase(settings_repository, cfg)

    settings = await upload_use_case(
        OWNER,
        UploadAppearanceImageInput(content_type="image/png", data=FAKE_PNG_APPEARANCE),
    )
    assert settings.has_logo is True

    data, content_type = await get_use_case.execute(AppearanceImageKind.LOGO)
    assert data == FAKE_PNG_APPEARANCE
    assert content_type == "image/png"


async def test_upload_rejects_svg_content_type(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    logo_use_case = UploadAppearanceLogoUseCase(settings_repository, cfg, uow)
    favicon_use_case = UploadAppearanceFaviconUseCase(settings_repository, cfg, uow)
    svg_data = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"

    with pytest.raises(ValidationError):
        await logo_use_case(
            OWNER, UploadAppearanceImageInput(content_type="image/svg+xml", data=svg_data)
        )

    with pytest.raises(ValidationError):
        await favicon_use_case(
            OWNER, UploadAppearanceImageInput(content_type="image/svg+xml", data=svg_data)
        )


async def test_upload_rejects_unsupported_content_type(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    use_case = UploadAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow
    )

    with pytest.raises(ValidationError):
        await use_case(OWNER, UploadAppearanceImageInput(content_type="application/pdf", data=b"x"))


async def test_upload_rejects_content_not_matching_declared_type(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    use_case = UploadAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadAppearanceImageInput(
                content_type="image/png",
                data=b"this is not actually a png",
            ),
        )


async def test_upload_rejects_oversized_file(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    use_case = UploadAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow
    )
    oversized = FAKE_PNG_APPEARANCE + b"x" * (2 * 1024 * 1024 + 1)

    with pytest.raises(ValidationError):
        await use_case(OWNER, UploadAppearanceImageInput(content_type="image/png", data=oversized))


async def test_get_appearance_image_missing_raises_not_found(
    settings_repository: SettingsRepository, config: AppConfig, tmp_path: Path
) -> None:
    use_case = GetPublicAppearanceImageUseCase(
        settings_repository, _appearance_config(config, tmp_path)
    )

    with pytest.raises(NotFoundError):
        await use_case.execute(AppearanceImageKind.LOGO)


async def test_owner_can_delete_uploaded_logo(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    upload_use_case = UploadAppearanceLogoUseCase(settings_repository, cfg, uow)
    delete_use_case = DeleteAppearanceLogoUseCase(settings_repository, cfg, uow)

    await upload_use_case(
        OWNER,
        UploadAppearanceImageInput(content_type="image/png", data=FAKE_PNG_APPEARANCE),
    )
    settings = await delete_use_case(OWNER)

    assert settings.has_logo is False
    assert not (tmp_path / "appearance" / "logo.png").exists()


async def test_delete_missing_appearance_image_raises_not_found(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    delete_use_case = DeleteAppearanceLogoUseCase(
        settings_repository, _appearance_config(config, tmp_path), uow
    )

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER)


async def test_admin_with_only_logo_permission_cannot_upload_favicon(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    logo_use_case = UploadAppearanceLogoUseCase(settings_repository, cfg, uow)
    favicon_use_case = UploadAppearanceFaviconUseCase(settings_repository, cfg, uow)
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
        UploadAppearanceImageInput(content_type="image/png", data=FAKE_PNG_APPEARANCE),
    )
    assert settings.has_logo is True

    with pytest.raises(PermissionDeniedError):
        await favicon_use_case(
            limited_admin,
            UploadAppearanceImageInput(content_type="image/png", data=FAKE_PNG_APPEARANCE),
        )


async def test_admin_with_upload_permission_cannot_delete(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    upload_use_case = UploadAppearanceLogoUseCase(settings_repository, cfg, uow)
    delete_use_case = DeleteAppearanceLogoUseCase(settings_repository, cfg, uow)
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
        UploadAppearanceImageInput(content_type="image/png", data=FAKE_PNG_APPEARANCE),
    )

    with pytest.raises(PermissionDeniedError):
        await delete_use_case(upload_only_admin, None)


async def test_admin_with_only_favicon_permission_cannot_upload_logo(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _appearance_config(config, tmp_path)
    logo_use_case = UploadAppearanceLogoUseCase(settings_repository, cfg, uow)
    favicon_use_case = UploadAppearanceFaviconUseCase(settings_repository, cfg, uow)
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
        UploadAppearanceImageInput(content_type="image/png", data=FAKE_PNG_APPEARANCE),
    )
    assert settings.has_favicon is True

    with pytest.raises(PermissionDeniedError):
        await logo_use_case(
            limited_admin,
            UploadAppearanceImageInput(content_type="image/png", data=FAKE_PNG_APPEARANCE),
        )
