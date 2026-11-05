import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from cryptography.fernet import Fernet

from app.cli.legacy.report import MigrationReport
from app.core.enums import Currency, PaymentGatewayType
from app.modules.gateways import GATEWAY_FIELD_CATALOG, is_gateway_configured

_TABLE: Final[str] = "payment_gateways"
_ENCRYPTED_PREFIX: Final[str] = "enc_"
_CURRENCY_KEY: Final[str] = "currency"
_CURRENCIES: Final[frozenset[Currency]] = frozenset({Currency.USD, Currency.RUB})


def decrypt_legacy(value: str, crypt_key: str) -> str:
    token = value.removeprefix(_ENCRYPTED_PREFIX).encode()
    return Fernet(crypt_key.encode()).decrypt(token).decode()


def _map_settings(
    gateway_type: PaymentGatewayType,
    old: Mapping[str, Any],
    *,
    currency: Currency,
    crypt_key: str,
    undecryptable: list[str],
) -> dict[str, str]:
    keys = {spec.key for spec in GATEWAY_FIELD_CATALOG[gateway_type]}
    values: dict[str, str] = {}
    for key, raw in old.items():
        if key not in keys or raw is None:
            continue
        value = str(raw)
        if value.startswith(_ENCRYPTED_PREFIX):
            try:
                value = decrypt_legacy(value, crypt_key)
            except Exception:
                undecryptable.append(key)
                continue
        values[key] = value
    if _CURRENCY_KEY in keys and _CURRENCY_KEY not in values and currency in _CURRENCIES:
        values[_CURRENCY_KEY] = currency.value
    return values


def transform_gateways(
    rows: Sequence[Mapping[str, Any]], *, crypt_key: str, report: MigrationReport
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: int(r["id"])):
        gateway_type = PaymentGatewayType(row["type"])
        undecryptable: list[str] = []
        values = _map_settings(
            gateway_type,
            row.get("settings") or {},
            currency=Currency(row["currency"]),
            crypt_key=crypt_key,
            undecryptable=undecryptable,
        )
        is_active = bool(row["is_active"])
        if undecryptable:
            is_active = False
            report.notes.append(
                f"{_TABLE}: {gateway_type.value} disabled, cannot decrypt {sorted(undecryptable)}"
            )
        elif not is_gateway_configured(gateway_type, values):
            if is_active:
                report.notes.append(
                    f"{_TABLE}: {gateway_type.value} disabled, required fields are missing"
                )
            is_active = False
        result.append(
            {
                "id": int(row["id"]),
                "type": gateway_type,
                "order_index": row["order_index"],
                "is_active": is_active,
                "settings": json.dumps(values) if values else None,
            }
        )
    report.count(_TABLE, len(rows), len(result))
    return result
