import pathlib
from decimal import Decimal

import pytest

from app.core.enums import PaymentOrderStatus
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
    amount_to_float,
    ip_in_networks,
)


def test_ip_in_networks_matches_cidr() -> None:
    assert ip_in_networks("91.227.144.54", ("91.227.144.0/24",)) is True


def test_ip_in_networks_rejects_outside_cidr() -> None:
    assert ip_in_networks("10.0.0.1", ("91.227.144.0/24",)) is False


def test_ip_in_networks_rejects_garbage_input() -> None:
    assert ip_in_networks("not-an-ip", ("91.227.144.0/24",)) is False
    assert ip_in_networks("91.227.144.54", ("bogus-net",)) is False


def test_amount_to_float_rounds_to_two_places() -> None:
    assert amount_to_float(Decimal("19.999")) == 20.0
    assert amount_to_float(Decimal("500")) == 500.0


def test_payment_gateway_is_abstract() -> None:
    with pytest.raises(TypeError):
        PaymentGateway(settings={}, webhook_url="x", return_url="y")  # type: ignore[abstract]


def test_dataclasses_are_frozen() -> None:
    intent = PaymentIntent(confirmation_url="https://pay", provider_payment_id="p1")
    with pytest.raises(Exception):
        intent.confirmation_url = "mutated"  # type: ignore[misc]
    result = WebhookResult(reference="ref", status=PaymentOrderStatus.PAID)
    assert result.provider_payment_id is None
    req = WebhookRequest(body=b"{}", headers={}, query={}, client_ip=None)
    assert req.body == b"{}"


def test_gateways_package_imports_no_web_framework() -> None:
    package = pathlib.Path(__file__).parents[4] / "app" / "modules" / "payments" / "gateways"
    assert (package / "base.py").is_file()
    offenders = []
    for path in package.glob("*.py"):
        text = path.read_text()
        for banned in ("fastapi", "aiogram"):
            if f"import {banned}" in text or f"from {banned}" in text:
                offenders.append(f"{path.name}: {banned}")
    assert offenders == [], offenders
