from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Final

from app.core.enums import Currency, PaymentGatewayType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError

_CURRENCY_FIELD_KEY: Final[str] = "currency"
# Webhook source-IP check for providers that don't sign their notifications
VERIFY_IP_FIELD_KEY: Final[str] = "verify_ip"
_BOOLEAN_VALUES: Final[frozenset[str]] = frozenset({"true", "false"})


class GatewayFieldKind(StrEnum):
    TEXT = auto()
    SECRET = auto()
    NUMBER = auto()
    BOOLEAN = auto()


@dataclass(frozen=True, kw_only=True)
class GatewayFieldSpec:
    key: str
    kind: GatewayFieldKind
    required: bool = True
    default: str = ""


GATEWAY_FIELD_CATALOG: Final[dict[PaymentGatewayType, tuple[GatewayFieldSpec, ...]]] = {
    # No settings (the bot token is enough), so is_gateway_configured() is
    # always True and it can be enabled with nothing behind it: no adapter in
    # GATEWAY_REGISTRY, no pre_checkout_query/successful_payment handler in
    # app/telegram. create_checkout refuses it; wire the bot side up before a
    # storefront offers it.
    PaymentGatewayType.TELEGRAM_STARS: (),
    PaymentGatewayType.YOOKASSA: (
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="vat_code", kind=GatewayFieldKind.NUMBER, required=False),
        GatewayFieldSpec(
            key=VERIFY_IP_FIELD_KEY, kind=GatewayFieldKind.BOOLEAN, required=False, default="true"
        ),
    ),
    PaymentGatewayType.YOOMONEY: (
        GatewayFieldSpec(key="wallet_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="access_token", kind=GatewayFieldKind.SECRET, required=False),
    ),
    PaymentGatewayType.CRYPTOMUS: (
        GatewayFieldSpec(key="merchant_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.HELEKET: (
        GatewayFieldSpec(key="merchant_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.CRYPTOPAY: (
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.FREEKASSA: (
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.NUMBER),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="secret_word_2", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="payment_system_id", kind=GatewayFieldKind.NUMBER),
    ),
    PaymentGatewayType.MULENPAY: (
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.NUMBER),
        GatewayFieldSpec(key="vat_code", kind=GatewayFieldKind.NUMBER, required=False),
    ),
    PaymentGatewayType.PAYMASTER: (
        GatewayFieldSpec(key="merchant_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
    ),
    PaymentGatewayType.PLATEGA: (
        GatewayFieldSpec(key="merchant_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="payment_method", kind=GatewayFieldKind.NUMBER, required=False),
    ),
    PaymentGatewayType.ROBOKASSA: (
        GatewayFieldSpec(key="merchant_login", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="password1", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="password2", kind=GatewayFieldKind.SECRET),
    ),
    PaymentGatewayType.URLPAY: (
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.NUMBER),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="vat_code", kind=GatewayFieldKind.NUMBER, required=False),
    ),
    PaymentGatewayType.WATA: (
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.VALUTIX: (
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="service_id", kind=GatewayFieldKind.NUMBER, required=False),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.ROLLYPAY: (
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="signing_secret", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.ANTILOPAY: (
        GatewayFieldSpec(key="secret_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="private_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="public_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="project_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.PAYPALYCH: (
        GatewayFieldSpec(key="api_token", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.RIOPAY: (
        GatewayFieldSpec(key="api_token", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="service_id", kind=GatewayFieldKind.NUMBER, required=False),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.AURAPAY: (
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
    ),
    PaymentGatewayType.SEVERPAY: (
        GatewayFieldSpec(key="mid", kind=GatewayFieldKind.NUMBER),
        GatewayFieldSpec(key="token", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.LAVA: (
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="webhook_secret", kind=GatewayFieldKind.SECRET),
    ),
    PaymentGatewayType.CLOUDPAYMENTS: (
        GatewayFieldSpec(key="public_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_secret", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.PAYPEAR: (
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
}


def is_gateway_configured(gateway_type: PaymentGatewayType, values: dict[str, str]) -> bool:
    return all(
        values.get(field_spec.key, "").strip() != ""
        for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]
        if field_spec.required
    )


def gateway_flags(gateway_type: PaymentGatewayType, values: dict[str, str]) -> dict[str, bool]:
    # unlike every other field these aren't secrets, so the dashboard reads
    # them back and renders switches
    return {
        field_spec.key: (values.get(field_spec.key) or field_spec.default) == "true"
        for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]
        if field_spec.kind is GatewayFieldKind.BOOLEAN
    }


def validate_gateway_field_keys(gateway_type: PaymentGatewayType, values: dict[str, str]) -> None:
    valid_keys = {field_spec.key for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]}
    unknown = set(values) - valid_keys
    if unknown:
        raise ValidationError(
            f"Unknown settings field(s) for {gateway_type.value}: {', '.join(sorted(unknown))}",
            code=ErrorCode.GATEWAY_FIELD_UNKNOWN,
        )


def validate_gateway_field_values(gateway_type: PaymentGatewayType, values: dict[str, str]) -> None:
    raw_currency = values.get(_CURRENCY_FIELD_KEY, "").strip()
    if raw_currency:
        try:
            Currency(raw_currency.upper())
        except ValueError:
            allowed = ", ".join(currency.value for currency in Currency)
            raise ValidationError(
                f"Invalid currency '{raw_currency}' for {gateway_type.value}; "
                f"must be one of {allowed}",
                code=ErrorCode.GATEWAY_CURRENCY_INVALID,
            ) from None

    for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]:
        if field_spec.kind is GatewayFieldKind.BOOLEAN:
            raw_flag = values.get(field_spec.key)
            if raw_flag is not None and raw_flag not in _BOOLEAN_VALUES:
                raise ValidationError(
                    f"Field '{field_spec.key}' for {gateway_type.value} must be 'true' or 'false'",
                    code=ErrorCode.GATEWAY_FIELD_NOT_BOOLEAN,
                )
            continue
        if field_spec.kind is not GatewayFieldKind.NUMBER:
            continue
        raw_value = values.get(field_spec.key, "").strip()
        if not raw_value:
            continue
        try:
            int(raw_value)
        except ValueError:
            raise ValidationError(
                f"Field '{field_spec.key}' for {gateway_type.value} must be a number, "
                f"got '{raw_value}'",
                code=ErrorCode.GATEWAY_FIELD_NOT_NUMBER,
            ) from None
