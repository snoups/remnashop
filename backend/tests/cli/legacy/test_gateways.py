import json
from typing import Any

from cryptography.fernet import Fernet

from app.cli.legacy.gateways import decrypt_legacy, transform_gateways
from app.cli.legacy.report import MigrationReport
from app.core.enums import PaymentGatewayType

KEY = Fernet.generate_key().decode()


def _enc(value: str) -> str:
    return "enc_" + Fernet(KEY.encode()).encrypt(value.encode()).decode()


def _row(gateway_type: str, settings: Any, **extra: Any) -> dict[str, Any]:
    row = {
        "id": 1,
        "type": gateway_type,
        "order_index": 2,
        "currency": "RUB",
        "is_active": True,
        "settings": settings,
    }
    row.update(extra)
    return row


def test_decrypt_legacy_roundtrip() -> None:
    assert decrypt_legacy(_enc("secret"), KEY) == "secret"


def test_yookassa_keys_mapped() -> None:
    settings = {
        "type": "YOOKASSA",
        "display_name": "Cards",
        "api_key": _enc("k"),
        "shop_id": "123",
        "customer": "a@b.c",
        "vat_code": 1,
    }
    item = transform_gateways(
        [_row("YOOKASSA", settings)], crypt_key=KEY, report=MigrationReport()
    )[0]
    assert json.loads(item["settings"]) == {"api_key": "k", "shop_id": "123", "vat_code": "1"}
    assert item["type"] is PaymentGatewayType.YOOKASSA
    assert item["is_active"] is True
    assert item["id"] == 1


def test_currency_goes_to_catalog_field() -> None:
    settings = {"api_key": _enc("k")}
    item = transform_gateways([_row("WATA", settings)], crypt_key=KEY, report=MigrationReport())[0]
    assert json.loads(item["settings"]) == {"api_key": "k", "currency": "RUB"}


def test_unmappable_gateway_disabled() -> None:
    report = MigrationReport()
    item = transform_gateways([_row("YOOKASSA", {"shop_id": "1"})], crypt_key=KEY, report=report)[0]
    assert item["is_active"] is False
    assert any("YOOKASSA" in note for note in report.notes)


def test_empty_settings_disabled() -> None:
    item = transform_gateways([_row("ROBOKASSA", None)], crypt_key=KEY, report=MigrationReport())[0]
    assert item["is_active"] is False
    assert item["settings"] is None


def test_broken_secret_disables_gateway() -> None:
    report = MigrationReport()
    settings = {"api_key": "enc_gAAAAbroken", "shop_id": "1"}
    item = transform_gateways([_row("YOOKASSA", settings)], crypt_key=KEY, report=report)[0]
    assert item["is_active"] is False
    assert "enc_" not in (item["settings"] or "")
    assert any("decrypt" in note for note in report.notes)


def test_stars_without_settings_stays_active() -> None:
    item = transform_gateways(
        [_row("TELEGRAM_STARS", {"type": "TELEGRAM_STARS"})],
        crypt_key=KEY,
        report=MigrationReport(),
    )[0]
    assert item["is_active"] is True
