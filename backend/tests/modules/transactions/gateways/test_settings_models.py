import pytest

from app.core.enums import PaymentGatewayType
from app.modules.gateways.field_catalog import GATEWAY_FIELD_CATALOG, GatewayFieldKind
from app.modules.gateways.gateway_settings import GATEWAY_SETTINGS
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY
from app.modules.transactions.gateways.telegram_stars import (
    BOT_PROXY_SETTING,
    BOT_TOKEN_SETTING,
    StarsRuntimeSettings,
    TelegramStarsSettings,
    with_bot_settings,
)

_SAMPLE: dict[GatewayFieldKind, str] = {
    GatewayFieldKind.TEXT: "text",
    GatewayFieldKind.SECRET: "secret",
    GatewayFieldKind.NUMBER: "42",
    GatewayFieldKind.BOOLEAN: "true",
}


def _full_form(gateway_type: PaymentGatewayType) -> dict[str, str]:
    return {spec.key: _SAMPLE[spec.kind] for spec in GATEWAY_FIELD_CATALOG[gateway_type]}


@pytest.mark.parametrize("gateway_type", list(GATEWAY_REGISTRY), ids=lambda t: t.value)
def test_gateway_reads_the_model_its_dashboard_form_is_built_from(
    gateway_type: PaymentGatewayType,
) -> None:
    assert issubclass(GATEWAY_REGISTRY[gateway_type].settings_model, GATEWAY_SETTINGS[gateway_type])


@pytest.mark.parametrize("gateway_type", list(GATEWAY_REGISTRY), ids=lambda t: t.value)
def test_a_complete_form_parses(gateway_type: PaymentGatewayType) -> None:
    values = _full_form(gateway_type)
    if gateway_type is PaymentGatewayType.TELEGRAM_STARS:
        values = with_bot_settings(values, "1:token", None)
    gateway = GATEWAY_REGISTRY[gateway_type](
        settings=values,
        webhook_url="https://example.com/hook",
        return_url="https://example.com",
        http=PaymentHttpClient(None),  # type: ignore[arg-type]
    )

    assert gateway.settings is not None


def test_stars_runtime_fields_are_the_ones_with_bot_settings_adds() -> None:
    added = set(StarsRuntimeSettings.model_fields) - set(TelegramStarsSettings.model_fields)

    assert added == {BOT_TOKEN_SETTING, BOT_PROXY_SETTING}
