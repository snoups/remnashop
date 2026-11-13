from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Final, Literal, get_args, get_origin

from pydantic import SecretStr
from pydantic.fields import FieldInfo

from app.core.enums import Currency, PaymentGatewayType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.gateways.gateway_settings import (
    GATEWAY_SETTINGS,
    NumericStr,
    yookassa_payment_mode,
)

_CURRENCY_FIELD_KEY: Final[str] = "currency"
# Stars settle only through the Telegram Stars gateway, which has no currency field
_GATEWAY_CURRENCIES: Final[tuple[Currency, ...]] = (Currency.USD, Currency.RUB)
# Webhook source-IP check for providers that don't sign their notifications
VERIFY_IP_FIELD_KEY: Final[str] = "verify_ip"
REQUIRE_PAID_PURCHASE_FIELD_KEY: Final[str] = "require_paid_purchase"
_BOOLEAN_VALUES: Final[frozenset[str]] = frozenset({"true", "false"})


class GatewayFieldKind(StrEnum):
    TEXT = auto()
    SECRET = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    CHOICE = auto()


@dataclass(frozen=True, kw_only=True)
class GatewayFieldSpec:
    key: str
    kind: GatewayFieldKind
    required: bool = True
    default: str = ""
    options: tuple[str, ...] = ()


_KIND_BY_TYPE: Final[dict[object, GatewayFieldKind]] = {
    str: GatewayFieldKind.TEXT,
    SecretStr: GatewayFieldKind.SECRET,
    NumericStr: GatewayFieldKind.NUMBER,
    bool: GatewayFieldKind.BOOLEAN,
}


def _field_spec(key: str, field: FieldInfo) -> GatewayFieldSpec:
    if get_origin(field.annotation) is Literal:
        return GatewayFieldSpec(
            key=key,
            kind=GatewayFieldKind.CHOICE,
            required=field.is_required(),
            default=str(field.default),
            options=get_args(field.annotation),
        )
    declared = [arg for arg in get_args(field.annotation) if arg is not type(None)]
    kind = _KIND_BY_TYPE[declared[0] if declared else field.annotation]
    default = str(field.default).lower() if kind is GatewayFieldKind.BOOLEAN else ""
    return GatewayFieldSpec(key=key, kind=kind, required=field.is_required(), default=default)


GATEWAY_FIELD_CATALOG: Final[dict[PaymentGatewayType, tuple[GatewayFieldSpec, ...]]] = {
    gateway_type: tuple(_field_spec(key, field) for key, field in model.model_fields.items())
    for gateway_type, model in GATEWAY_SETTINGS.items()
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
    flags = {
        field_spec.key: (values.get(field_spec.key) or field_spec.default) == "true"
        for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]
        if field_spec.kind is GatewayFieldKind.BOOLEAN
    }
    if gateway_type is PaymentGatewayType.YOOKASSA:
        mode = yookassa_payment_mode(values)
        flags["recurring_enabled"] = mode != "single"
        flags["recurring_required"] = mode == "recurring"
    return flags


def validate_gateway_field_keys(gateway_type: PaymentGatewayType, values: dict[str, str]) -> None:
    valid_keys = {field_spec.key for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]}
    if gateway_type is PaymentGatewayType.YOOKASSA:
        valid_keys.add("recurring_enabled")  # Older clients can still send the legacy switch.
    unknown = set(values) - valid_keys
    if unknown:
        raise ValidationError(
            f"Unknown settings field(s) for {gateway_type.value}: {', '.join(sorted(unknown))}",
            code=ErrorCode.GATEWAY_FIELD_UNKNOWN,
        )


def validate_gateway_field_values(gateway_type: PaymentGatewayType, values: dict[str, str]) -> None:
    raw_currency = values.get(_CURRENCY_FIELD_KEY, "").strip()
    if raw_currency:
        if raw_currency.upper() not in _GATEWAY_CURRENCIES:
            allowed = ", ".join(currency.value for currency in _GATEWAY_CURRENCIES)
            raise ValidationError(
                f"Invalid currency '{raw_currency}' for {gateway_type.value}; "
                f"must be one of {allowed}",
                code=ErrorCode.GATEWAY_CURRENCY_INVALID,
            )

    if gateway_type is PaymentGatewayType.YOOKASSA and "recurring_enabled" in values:
        if values["recurring_enabled"] not in _BOOLEAN_VALUES:
            raise ValidationError(
                "recurring_enabled must be 'true' or 'false'",
                code=ErrorCode.GATEWAY_FIELD_NOT_BOOLEAN,
            )
    for field_spec in GATEWAY_FIELD_CATALOG[gateway_type]:
        _validate_field_value(gateway_type, field_spec, values.get(field_spec.key))


def _validate_field_value(
    gateway_type: PaymentGatewayType, field_spec: GatewayFieldSpec, raw_value: str | None
) -> None:
    if field_spec.kind is GatewayFieldKind.CHOICE:
        if raw_value is not None and raw_value not in field_spec.options:
            raise ValidationError(
                f"Invalid choice for '{field_spec.key}'",
                code=ErrorCode.GATEWAY_FIELD_INVALID_CHOICE,
            )
        return
    if field_spec.kind is GatewayFieldKind.BOOLEAN:
        if raw_value is not None and raw_value not in _BOOLEAN_VALUES:
            raise ValidationError(
                f"Field '{field_spec.key}' for {gateway_type.value} must be 'true' or 'false'",
                code=ErrorCode.GATEWAY_FIELD_NOT_BOOLEAN,
            )
        return
    if field_spec.kind is not GatewayFieldKind.NUMBER or not raw_value or not raw_value.strip():
        return
    try:
        int(raw_value)
    except ValueError:
        raise ValidationError(
            f"Field '{field_spec.key}' for {gateway_type.value} must be a number, "
            f"got '{raw_value}'",
            code=ErrorCode.GATEWAY_FIELD_NOT_NUMBER,
        ) from None
