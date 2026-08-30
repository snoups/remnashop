import pytest

from app.core.enums import PaymentGatewayType
from app.core.exceptions import ValidationError
from app.modules.gateways.field_catalog import (
    GATEWAY_FIELD_CATALOG,
    is_gateway_configured,
    validate_gateway_field_keys,
)


def test_all_gateway_types_have_a_catalog_entry() -> None:
    assert set(GATEWAY_FIELD_CATALOG) == set(PaymentGatewayType)


def test_telegram_stars_has_no_fields_and_is_always_configured() -> None:
    assert GATEWAY_FIELD_CATALOG[PaymentGatewayType.TELEGRAM_STARS] == ()
    assert is_gateway_configured(PaymentGatewayType.TELEGRAM_STARS, {})


def test_is_gateway_configured_false_when_required_field_missing() -> None:
    assert not is_gateway_configured(PaymentGatewayType.YOOKASSA, {"shop_id": "123"})


def test_is_gateway_configured_true_when_required_fields_present() -> None:
    assert is_gateway_configured(
        PaymentGatewayType.YOOKASSA, {"shop_id": "123", "api_key": "secret"}
    )


def test_is_gateway_configured_ignores_optional_fields() -> None:
    assert is_gateway_configured(
        PaymentGatewayType.YOOKASSA, {"shop_id": "123", "api_key": "secret", "customer": ""}
    )


def test_is_gateway_configured_treats_blank_required_field_as_missing() -> None:
    assert not is_gateway_configured(
        PaymentGatewayType.YOOKASSA, {"shop_id": "123", "api_key": "   "}
    )


def test_validate_gateway_field_keys_accepts_known_keys() -> None:
    validate_gateway_field_keys(PaymentGatewayType.YOOKASSA, {"shop_id": "123"})  # does not raise


def test_validate_gateway_field_keys_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        validate_gateway_field_keys(PaymentGatewayType.YOOKASSA, {"bogus_field": "x"})


def test_platega_payment_method_is_optional() -> None:
    assert is_gateway_configured(PaymentGatewayType.PLATEGA, {"merchant_id": "m1", "api_key": "k1"})
