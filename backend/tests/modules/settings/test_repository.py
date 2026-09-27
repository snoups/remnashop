from dataclasses import fields as dataclass_fields

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.oauth_settings import OAuthSettings
from app.core.enums import AppearanceImageKind, AppearanceResetScope, Locale
from app.core.exceptions import ConflictError
from app.modules.settings.dto import (
    UpdateAppearanceSettingsDto,
    UpdateBotSettingsDto,
    UpdateOAuthSettingsDto,
    UpdateShopSettingsDto,
)
from app.modules.settings.repository import SettingsRepository


async def test_get_bot_settings_defaults_to_unconfigured(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.get_bot_settings()

    assert settings.token is None
    assert settings.secret_token is None
    assert not settings.is_configured


async def test_update_then_get_roundtrips_decrypted_values(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_bot_settings(
        UpdateBotSettingsDto(
            token="123:abcdef", secret_token="webhook-secret", drop_pending_updates=None
        )
    )

    settings = await settings_repository.get_bot_settings()

    assert settings.token is not None
    assert settings.token.get_secret_value() == "123:abcdef"
    assert settings.secret_token is not None
    assert settings.secret_token.get_secret_value() == "webhook-secret"
    assert settings.is_configured


async def test_partial_update_leaves_other_field_untouched(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_bot_settings(
        UpdateBotSettingsDto(
            token="123:abcdef", secret_token="webhook-secret", drop_pending_updates=None
        )
    )

    await settings_repository.update_bot_settings(
        UpdateBotSettingsDto(token="999:newtoken", secret_token=None, drop_pending_updates=None)
    )

    settings = await settings_repository.get_bot_settings()
    assert settings.token is not None
    assert settings.token.get_secret_value() == "999:newtoken"
    assert settings.secret_token is not None
    assert settings.secret_token.get_secret_value() == "webhook-secret"


async def test_stored_value_is_encrypted_at_rest(
    settings_repository: SettingsRepository, session: AsyncSession
) -> None:
    await settings_repository.update_bot_settings(
        UpdateBotSettingsDto(
            token="123:abcdef", secret_token="webhook-secret", drop_pending_updates=None
        )
    )

    # Raw SQL, not session.get(BotSettings, ...) -- the ORM path runs the
    # EncryptedString type decorator and would transparently decrypt back to
    # plaintext, which is exactly the behavior this test needs to see past.
    row = (
        await session.execute(text("SELECT token, secret_token FROM bot_settings WHERE id = 1"))
    ).one()
    assert row.token != "123:abcdef"
    assert row.secret_token != "webhook-secret"


async def test_get_oauth_settings_defaults_to_unconfigured(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.get_oauth_settings()

    assert settings.github_client_id is None
    assert not settings.is_github_configured
    assert not settings.is_telegram_configured
    assert settings.password_login_enabled is True


async def test_get_oauth_settings_passkey_defaults_to_disabled(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.get_oauth_settings()

    assert settings.passkey_enabled is False
    assert settings.passkey_rp_id is None
    assert not settings.is_passkey_configured
    assert not settings.is_passkey_usable


async def test_update_then_get_oauth_settings_roundtrips_passkey_fields(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            passkey_enabled=True,
            passkey_rp_id="example.com",
            passkey_origin="https://example.com",
        )
    )

    settings = await settings_repository.get_oauth_settings()
    assert settings.passkey_enabled is True
    assert settings.passkey_rp_id == "example.com"
    assert settings.passkey_origin == "https://example.com"
    assert settings.is_passkey_configured
    assert settings.is_passkey_usable


async def test_password_login_toggle_roundtrips(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(password_login_enabled=False)
    )

    settings = await settings_repository.get_oauth_settings()
    assert settings.password_login_enabled is False

    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(password_login_enabled=True)
    )

    settings = await settings_repository.get_oauth_settings()
    assert settings.password_login_enabled is True


async def test_update_then_get_oauth_settings_roundtrips_decrypted_values(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            github_client_id="gh-id",
            github_client_secret="gh-secret",
            telegram_client_id="tg-id",
            telegram_client_secret="tg-secret",
        )
    )

    settings = await settings_repository.get_oauth_settings()

    assert settings.github_client_id == "gh-id"
    assert settings.github_client_secret is not None
    assert settings.github_client_secret.get_secret_value() == "gh-secret"
    assert settings.telegram_client_id == "tg-id"
    assert settings.telegram_client_secret is not None
    assert settings.telegram_client_secret.get_secret_value() == "tg-secret"
    assert settings.is_github_configured
    assert settings.is_telegram_configured


async def test_oauth_settings_partial_update_leaves_other_fields_untouched(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            github_client_id="gh-id",
            github_client_secret="gh-secret",
            telegram_client_id=None,
            telegram_client_secret=None,
        )
    )

    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            github_client_id=None,
            github_client_secret=None,
            telegram_client_id="tg-id",
            telegram_client_secret="tg-secret",
        )
    )

    settings = await settings_repository.get_oauth_settings()
    assert settings.github_client_id == "gh-id"
    assert settings.telegram_client_id == "tg-id"


async def test_oauth_settings_stored_value_is_encrypted_at_rest(
    settings_repository: SettingsRepository, session: AsyncSession
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            github_client_id="gh-id",
            github_client_secret="gh-secret",
            telegram_client_id=None,
            telegram_client_secret=None,
        )
    )

    row = (
        await session.execute(
            text("SELECT github_client_id, github_client_secret FROM oauth_settings WHERE id = 1")
        )
    ).one()
    assert row.github_client_id != "gh-id"
    assert row.github_client_secret != "gh-secret"


async def test_get_oauth_settings_oidc_defaults_to_unconfigured(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.get_oauth_settings()

    assert settings.oidc_issuer_url is None
    assert not settings.is_oidc_configured


async def test_update_then_get_oidc_settings_roundtrips_decrypted_values(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            oidc_issuer_url="https://keycloak.example.com/realms/myrealm",
            oidc_client_id="oidc-id",
            oidc_client_secret="oidc-secret",
            oidc_display_name="Keycloak",
        )
    )

    settings = await settings_repository.get_oauth_settings()

    assert settings.oidc_issuer_url == "https://keycloak.example.com/realms/myrealm"
    assert settings.oidc_client_id == "oidc-id"
    assert settings.oidc_client_secret is not None
    assert settings.oidc_client_secret.get_secret_value() == "oidc-secret"
    assert settings.oidc_display_name == "Keycloak"
    assert settings.is_oidc_configured


async def test_oidc_configured_requires_display_name(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            oidc_issuer_url="https://keycloak.example.com/realms/myrealm",
            oidc_client_id="oidc-id",
            oidc_client_secret="oidc-secret",
        )
    )

    settings = await settings_repository.get_oauth_settings()

    assert not settings.is_oidc_configured


async def test_oidc_settings_stored_value_is_encrypted_at_rest(
    settings_repository: SettingsRepository, session: AsyncSession
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            oidc_issuer_url="https://keycloak.example.com/realms/myrealm",
            oidc_client_id="oidc-id",
            oidc_client_secret="oidc-secret",
            oidc_display_name="Keycloak",
        )
    )

    row = (
        await session.execute(
            text(
                "SELECT oidc_issuer_url, oidc_client_id, oidc_client_secret, oidc_display_name "
                "FROM oauth_settings WHERE id = 1"
            )
        )
    ).one()
    # issuer_url/display_name are plain columns -- not secrets, stored as-is.
    assert row.oidc_issuer_url == "https://keycloak.example.com/realms/myrealm"
    assert row.oidc_display_name == "Keycloak"
    # client_id/client_secret go through EncryptedString -- must not be plaintext at rest.
    assert row.oidc_client_id != "oidc-id"
    assert row.oidc_client_secret != "oidc-secret"


def test_update_oauth_dto_fields_all_map_to_columns() -> None:
    column_names = set(OAuthSettings.__mapper__.attrs.keys())
    dto_field_names = {field.name for field in dataclass_fields(UpdateOAuthSettingsDto)}
    assert dto_field_names <= column_names


async def test_replace_bot_commands_persists_enabled_flag(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.replace_bot_commands([("menu", True), ("help", False)])

    commands = await settings_repository.list_bot_commands()

    by_command = {item.command: item for item in commands}
    assert by_command["menu"].enabled is True
    assert by_command["help"].enabled is False


async def test_add_and_list_active_locales(settings_repository: SettingsRepository) -> None:
    await settings_repository.add_active_locale(Locale.EN)
    await settings_repository.add_active_locale(Locale.RU)

    locales = await settings_repository.list_active_locales()

    assert set(locales) == {Locale.EN, Locale.RU}


async def test_add_active_locale_rejects_duplicate(settings_repository: SettingsRepository) -> None:
    await settings_repository.add_active_locale(Locale.EN)

    with pytest.raises(ConflictError):
        await settings_repository.add_active_locale(Locale.EN)


async def test_remove_active_locale(settings_repository: SettingsRepository) -> None:
    await settings_repository.add_active_locale(Locale.EN)
    await settings_repository.add_active_locale(Locale.RU)

    await settings_repository.remove_active_locale(Locale.RU)

    assert await settings_repository.list_active_locales() == [Locale.EN]


async def test_get_appearance_settings_returns_defaults_when_missing(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.get_appearance_settings()

    assert settings.brand_name is None
    assert settings.primary_color is None
    assert settings.shader_palette is None
    assert settings.shader_enabled is True
    assert settings.has_logo is False
    assert settings.has_favicon is False


async def test_update_appearance_settings_persists_partial_updates(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_appearance_settings(
        UpdateAppearanceSettingsDto(brand_name="Acme VPN")
    )
    settings = await settings_repository.update_appearance_settings(
        UpdateAppearanceSettingsDto(
            primary_color="#ff0000",
            shader_palette=["#111111", "#222222", "#333333", "#444444"],
            shader_enabled=False,
        )
    )

    assert settings.brand_name == "Acme VPN"
    assert settings.primary_color == "#ff0000"
    assert settings.shader_palette == ["#111111", "#222222", "#333333", "#444444"]
    assert settings.shader_enabled is False


async def test_reset_appearance_settings_clears_only_its_scope(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_appearance_settings(
        UpdateAppearanceSettingsDto(
            brand_name="Acme VPN",
            primary_color="#ff0000",
            shader_palette=["#111111", "#222222", "#333333", "#444444"],
            shader_enabled=False,
        )
    )
    settings = await settings_repository.reset_appearance_settings(AppearanceResetScope.BRANDING)

    assert settings.brand_name is None
    assert settings.primary_color == "#ff0000"
    assert settings.shader_enabled is False

    settings = await settings_repository.reset_appearance_settings(AppearanceResetScope.COLORS)

    assert settings.primary_color is None
    assert settings.shader_palette is None
    assert settings.shader_enabled is True


async def test_set_appearance_image_marks_has_logo(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.set_appearance_image(
        AppearanceImageKind.LOGO, "image/png", "png"
    )

    assert settings.has_logo is True
    assert settings.has_favicon is False
    meta = await settings_repository.get_appearance_image_meta(AppearanceImageKind.LOGO)
    assert meta == ("png", "image/png")


async def test_get_appearance_image_meta_returns_none_when_unset(
    settings_repository: SettingsRepository,
) -> None:
    meta = await settings_repository.get_appearance_image_meta(AppearanceImageKind.FAVICON)
    assert meta is None


async def test_clear_appearance_image_resets_has_logo(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.set_appearance_image(AppearanceImageKind.LOGO, "image/png", "png")
    settings = await settings_repository.clear_appearance_image(AppearanceImageKind.LOGO)

    assert settings.has_logo is False
    assert await settings_repository.get_appearance_image_meta(AppearanceImageKind.LOGO) is None


async def test_set_appearance_image_kinds_are_independent(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.set_appearance_image(AppearanceImageKind.LOGO, "image/png", "png")
    settings = await settings_repository.set_appearance_image(
        AppearanceImageKind.FAVICON, "image/svg+xml", "svg"
    )

    assert settings.has_logo is True
    assert settings.has_favicon is True


async def test_get_shop_settings_defaults_to_three(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.get_shop_settings()

    assert settings.max_active_subscriptions == 3


async def test_update_shop_settings_to_unlimited(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=None,
            device_single_reset_enabled=True,
            device_single_reset_cooldown_hours=0,
            device_all_reset_enabled=True,
            device_all_reset_cooldown_hours=0,
            link_reset_enabled=True,
            link_reset_cooldown_hours=0,
        )
    )

    assert settings.max_active_subscriptions is None
    assert (await settings_repository.get_shop_settings()).max_active_subscriptions is None


async def test_update_shop_settings_to_a_specific_cap(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=10,
            device_single_reset_enabled=True,
            device_single_reset_cooldown_hours=0,
            device_all_reset_enabled=True,
            device_all_reset_cooldown_hours=0,
            link_reset_enabled=True,
            link_reset_cooldown_hours=0,
        )
    )

    assert settings.max_active_subscriptions == 10


async def test_shop_settings_round_trips_reset_cooldowns(
    settings_repository: SettingsRepository,
) -> None:
    default = await settings_repository.get_shop_settings()
    assert default.device_single_reset_enabled is True
    assert default.device_single_reset_cooldown_hours == 0

    updated = await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=default.max_active_subscriptions,
            device_single_reset_enabled=False,
            device_single_reset_cooldown_hours=12,
            device_all_reset_enabled=True,
            device_all_reset_cooldown_hours=24,
            link_reset_enabled=True,
            link_reset_cooldown_hours=6,
        )
    )

    assert updated.device_single_reset_enabled is False
    assert updated.device_single_reset_cooldown_hours == 12
    assert updated.device_all_reset_cooldown_hours == 24
    assert updated.link_reset_cooldown_hours == 6
