from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Final

from app.core.enums import PaymentGatewayType
from app.core.exceptions import ValidationError


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
    ),
    PaymentGatewayType.HELEKET: (
        GatewayFieldSpec(key="merchant_id", kind=GatewayFieldKind.TEXT),
        GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),
    ),
    PaymentGatewayType.CRYPTOPAY: (GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),),
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
    PaymentGatewayType.WATA: (GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),),
    PaymentGatewayType.VALUTIX: (GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),),
    # Not present in the pre-rebuild codebase (no rollypay.py there) --
    # placeholder field set, confirm against RollyPay's real API before
    # wiring an actual provider integration.
    PaymentGatewayType.ROLLYPAY: (GatewayFieldSpec(key="api_key", kind=GatewayFieldKind.SECRET),),
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
