from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Final, get_args

from pydantic import SecretStr
from pydantic.fields import FieldInfo

from app.core.enums import Currency, PaymentGatewayType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.gateways.gateway_settings import GATEWAY_SETTINGS, NumericStr

_CURRENCY_FIELD_KEY: Final[str] = "currency"
# Webhook source-IP check for providers that don't sign their notifications
VERIFY_IP_FIELD_KEY: Final[str] = "verify_ip"
REQUIRE_PAID_PURCHASE_FIELD_KEY: Final[str] = "require_paid_purchase"
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


_KIND_BY_TYPE: Final[dict[object, GatewayFieldKind]] = {
    str: GatewayFieldKind.TEXT,
    SecretStr: GatewayFieldKind.SECRET,
    NumericStr: GatewayFieldKind.NUMBER,
    bool: GatewayFieldKind.BOOLEAN,
}


def _field_spec(key: str, field: FieldInfo) -> GatewayFieldSpec:
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
