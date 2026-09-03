from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Final

from app.core.enums import Currency, PaymentGatewayType
from app.core.exceptions import ValidationError

_CURRENCY_FIELD_KEY: Final[str] = "currency"


class GatewayFieldKind(StrEnum):
    TEXT = auto()
    SECRET = auto()
    NUMBER = auto()


@dataclass(frozen=True, kw_only=True)
class GatewayFieldSpec:
    key: str
    kind: GatewayFieldKind
    required: bool = True


GATEWAY_FIELD_CATALOG: Final[dict[PaymentGatewayType, tuple[GatewayFieldSpec, ...]]] = {
    PaymentGatewayType.TELEGRAM_STARS: (),
    PaymentGatewayType.YOOKASSA: (
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="customer", kind=GatewayFieldKind.TEXT, required=False),
        GatewayFieldSpec(key="vat_code", kind=GatewayFieldKind.NUMBER, required=False),
    ),
    PaymentGatewayType.YOOMONEY: (
        GatewayFieldSpec(key="wallet_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
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
        GatewayFieldSpec(key="customer_email", kind=GatewayFieldKind.TEXT, required=False),
        GatewayFieldSpec(key="customer_ip", kind=GatewayFieldKind.TEXT, required=False),
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
        GatewayFieldSpec(key="signature_token", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.RIOPAY: (
        GatewayFieldSpec(key="api_token", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="webhook_secret", kind=GatewayFieldKind.SECRET, required=False),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.AURAPAY: (
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
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
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.CLOUDPAYMENTS: (
        GatewayFieldSpec(key="public_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_secret", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.KASSAAI: (
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.NUMBER),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="secret_word_2", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.PAYPEAR: (
        GatewayFieldSpec(key="shop_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.ETOPLATEZHI: (
        GatewayFieldSpec(key="project_id", kind=GatewayFieldKind.NUMBER),
        GatewayFieldSpec(key="secret_key", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.JUPITER: (
        GatewayFieldSpec(key="token", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="secret", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="method_id", kind=GatewayFieldKind.TEXT, required=False),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    PaymentGatewayType.DONUT: (
        GatewayFieldSpec(key="token", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="secret", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="method_id", kind=GatewayFieldKind.TEXT, required=False),
        GatewayFieldSpec(key="currency", kind=GatewayFieldKind.TEXT, required=False),
    ),
    # Overpay's real integration authenticates with a client-certificate
    # (.p12 + passphrase, mTLS) on top of username/password -- confirm the
    # exact handshake against Overpay's own API docs before wiring an
    # adapter; a plain api_key placeholder would be a lie about what it
    # actually needs.
    PaymentGatewayType.OVERPAY: (
        GatewayFieldSpec(key="username", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="password", kind=GatewayFieldKind.SECRET),
        GatewayFieldSpec(key="project_id", kind=GatewayFieldKind.TEXT),
    ),
    # A reference Tribute integration is a non-functional stub (hardcoded
    # payment_url, signature computed over str(dict) rather than the raw
    # webhook body) -- not something to port faithfully. Placeholder until
    # Tribute's real API is confirmed.
    PaymentGatewayType.TRIBUTE: (GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),),
}


def is_gateway_configured(gateway_type: PaymentGatewayType, values: dict[str, str]) -> bool:
    return all(
        values.get(field_spec.key, "").strip() != ""
        for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]
        if field_spec.required
    )


def validate_gateway_field_keys(gateway_type: PaymentGatewayType, values: dict[str, str]) -> None:
    valid_keys = {field_spec.key for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]}
    unknown = set(values) - valid_keys
    if unknown:
        raise ValidationError(
            f"Unknown settings field(s) for {gateway_type.value}: {', '.join(sorted(unknown))}"
        )


def validate_gateway_field_values(gateway_type: PaymentGatewayType, values: dict[str, str]) -> None:
    raw_currency = values.get(_CURRENCY_FIELD_KEY, "").strip()
    if not raw_currency:
        return
    try:
        Currency(raw_currency.upper())
    except ValueError:
        allowed = ", ".join(currency.value for currency in Currency)
        raise ValidationError(
            f"Invalid currency '{raw_currency}' for {gateway_type.value}; must be one of {allowed}"
        ) from None
