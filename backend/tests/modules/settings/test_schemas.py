import pytest
from pydantic import SecretStr, ValidationError

from app.modules.settings.api.schemas import (
    BotCommandItem,
    OAuthSettingsResponse,
    UpdateOAuthSettingsRequest,
)
from app.modules.settings.dto import BotSettingsDto


def test_update_oauth_settings_request_accepts_https_issuer_url() -> None:
    request = UpdateOAuthSettingsRequest(
        oidc_issuer_url="https://keycloak.example.com/realms/myrealm",
        oidc_client_id="oidc-id",
        oidc_client_secret="oidc-secret",
        oidc_display_name="Keycloak",
    )

    assert request.oidc_issuer_url == "https://keycloak.example.com/realms/myrealm"


def test_update_oauth_settings_request_rejects_non_https_issuer_url() -> None:
    with pytest.raises(ValidationError):
        UpdateOAuthSettingsRequest(oidc_issuer_url="http://keycloak.example.com/realms/myrealm")


def test_oauth_settings_response_carries_oidc_fields() -> None:
    response = OAuthSettingsResponse(
        is_github_configured=False,
        is_github_enabled=False,
        is_telegram_configured=False,
        is_telegram_enabled=False,
        is_oidc_configured=True,
        is_oidc_enabled=True,
        oidc_display_name="Keycloak",
        is_password_login_enabled=True,
    )

    assert response.is_oidc_configured
    assert response.oidc_display_name == "Keycloak"


def test_bot_command_item_carries_enabled_flag() -> None:
    item = BotCommandItem(command="menu", enabled=False)

    assert item.enabled is False


def test_bot_settings_token_is_masked_in_repr_and_str() -> None:
    dto = BotSettingsDto(token=SecretStr("123:ABCsecret"), secret_token=SecretStr("whsec"))

    assert "ABCsecret" not in repr(dto)
    assert "ABCsecret" not in str(dto)
    assert "whsec" not in repr(dto)
    assert dto.token is not None
    assert dto.token.get_secret_value() == "123:ABCsecret"


def test_bot_settings_is_configured_still_works_with_secretstr() -> None:
    assert BotSettingsDto(token=SecretStr("t"), secret_token=SecretStr("s")).is_configured
    assert not BotSettingsDto(token=SecretStr("t")).is_configured
    assert not BotSettingsDto().is_configured
