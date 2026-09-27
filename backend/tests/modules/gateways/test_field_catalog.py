import pytest

from app.core.enums import PaymentGatewayType
from app.core.exceptions import ValidationError
from app.modules.gateways.field_catalog import (
    GATEWAY_FIELD_CATALOG,
    is_gateway_configured,
    validate_gateway_field_keys,
    validate_gateway_field_values,
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
        PaymentGatewayType.YOOKASSA, {"shop_id": "123", "api_key": "secret", "vat_code": ""}
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


def test_validate_gateway_field_values_accepts_a_known_currency() -> None:
    validate_gateway_field_values(  # does not raise
        PaymentGatewayType.CRYPTOMUS, {"currency": "RUB"}
    )


def test_validate_gateway_field_values_accepts_lowercase_currency() -> None:
    validate_gateway_field_values(  # does not raise
        PaymentGatewayType.CRYPTOMUS, {"currency": "usd"}
    )


def test_validate_gateway_field_values_rejects_an_unknown_currency() -> None:
    with pytest.raises(ValidationError):
        validate_gateway_field_values(PaymentGatewayType.CRYPTOMUS, {"currency": "EUR"})


def test_validate_gateway_field_values_ignores_an_absent_currency() -> None:
    validate_gateway_field_values(PaymentGatewayType.YOOKASSA, {"shop_id": "1"})  # does not raise


def test_paypalych_signs_with_the_api_token_only() -> None:
    keys = {spec.key for spec in GATEWAY_FIELD_CATALOG[PaymentGatewayType.PAYPALYCH]}
    assert keys == {"api_token", "shop_id", "currency"}


def test_customer_email_and_ip_are_not_gateway_settings() -> None:
    for specs in GATEWAY_FIELD_CATALOG.values():
        keys = {spec.key for spec in specs}
        assert not keys & {"customer", "customer_email", "customer_ip"}


def test_riopay_and_valutix_take_an_optional_service_id() -> None:
    for gateway_type in (PaymentGatewayType.RIOPAY, PaymentGatewayType.VALUTIX):
        specs = {spec.key: spec for spec in GATEWAY_FIELD_CATALOG[gateway_type]}
        assert specs["service_id"].required is False
    riopay_keys = {spec.key for spec in GATEWAY_FIELD_CATALOG[PaymentGatewayType.RIOPAY]}
    assert "webhook_secret" not in riopay_keys


def test_yoomoney_access_token_is_optional() -> None:
    specs = {spec.key: spec for spec in GATEWAY_FIELD_CATALOG[PaymentGatewayType.YOOMONEY]}
    assert specs["access_token"].required is False


def test_aurapay_and_lava_are_rub_only_and_have_no_currency_field() -> None:
    for gateway_type in (PaymentGatewayType.AURAPAY, PaymentGatewayType.LAVA):
        keys = {spec.key for spec in GATEWAY_FIELD_CATALOG[gateway_type]}
        assert "currency" not in keys
