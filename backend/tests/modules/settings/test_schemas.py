import pytest
from pydantic import SecretStr, ValidationError

from app.modules.settings.api.schemas import (
    BotCommandRequest,
    OAuthSettingsResponse,
    UpdateBotRequirementsRequest,
    UpdateOAuthSettingsRequest,
    UpdateShopSettingsRequest,
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
        github_enabled=False,
        is_telegram_configured=False,
        is_google_configured=False,
        is_yandex_configured=False,
        telegram_enabled=False,
        is_oidc_configured=True,
        oidc_enabled=True,
        oidc_display_name="Keycloak",
        password_login_enabled=True,
        is_passkey_configured=False,
        passkey_enabled=False,
    )

    assert response.is_oidc_configured
    assert response.oidc_display_name == "Keycloak"


def test_bot_command_item_carries_enabled_flag() -> None:
    item = BotCommandRequest(command="menu", enabled=False)

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


def test_bot_requirements_channel_id_is_bounded_to_int64() -> None:
    UpdateBotRequirementsRequest(channel_id=-(2**63))
    with pytest.raises(ValidationError):
        UpdateBotRequirementsRequest(channel_id=-(2**63) - 1)


def test_bot_requirements_bare_channel_id_gets_the_channel_prefix() -> None:
    assert UpdateBotRequirementsRequest(channel_id=2344979239).channel_id == -1002344979239
    from_json = UpdateBotRequirementsRequest.model_validate({"channel_id": "2344979239"})
    assert from_json.channel_id == -1002344979239
    assert UpdateBotRequirementsRequest(channel_id=-1002344979239).channel_id == -1002344979239
    assert UpdateBotRequirementsRequest(channel_id=None).channel_id is None
    # a prefixed id past int64 is still refused
    with pytest.raises(ValidationError):
        UpdateBotRequirementsRequest(channel_id=2**63 - 1)


def test_bot_requirements_channel_url_takes_telegram_links_only() -> None:
    def url(value: str) -> str:
        return str(UpdateBotRequirementsRequest(channel_url=value).channel_url)  # type: ignore[arg-type]

    assert url("t.me/+QKLgLpiCXhxmYTc6") == "https://t.me/+QKLgLpiCXhxmYTc6"
    assert url("https://t.me/mychannel") == "https://t.me/mychannel"
    assert url("https://telegram.me/mychannel") == "https://telegram.me/mychannel"
    for value in ("https://example.com/channel", "tg://join?invite=abc"):
        with pytest.raises(ValidationError):
            UpdateBotRequirementsRequest(channel_url=value)  # type: ignore[arg-type]


def test_update_shop_settings_request_tracks_sent_fields() -> None:
    request = UpdateShopSettingsRequest.model_validate({"max_active_subscriptions": None})

    assert request.model_fields_set == {"max_active_subscriptions"}


def test_update_shop_settings_request_rejects_null_for_non_nullable_fields() -> None:
    with pytest.raises(ValidationError):
        UpdateShopSettingsRequest.model_validate({"link_reset_enabled": None})


@pytest.mark.parametrize(
    "typed", ["shop_help", "@shop_help", "t.me/shop_help", "https://t.me/shop_help/"]
)
def test_update_shop_settings_request_keeps_the_support_username(typed: str) -> None:
    request = UpdateShopSettingsRequest.model_validate({"support_telegram": typed})
    assert request.support_telegram == "shop_help"


@pytest.mark.parametrize("typed", ["sh", "https://example.com/shop_help", "shop help"])
def test_update_shop_settings_request_rejects_a_bad_support_username(typed: str) -> None:
    with pytest.raises(ValidationError):
        UpdateShopSettingsRequest.model_validate({"support_telegram": typed})


def test_update_shop_settings_request_wants_an_https_support_url() -> None:
    with pytest.raises(ValidationError):
        UpdateShopSettingsRequest.model_validate({"support_url": "http://help.example.com"})
    request = UpdateShopSettingsRequest.model_validate({"support_url": "https://help.example.com"})
    assert request.support_url == "https://help.example.com"


def test_update_shop_settings_request_clears_support_with_a_blank() -> None:
    request = UpdateShopSettingsRequest.model_validate({"support_telegram": " ", "support_url": ""})
    assert request.support_telegram is None
    assert request.support_url is None
    assert request.model_fields_set == {"support_telegram", "support_url"}
