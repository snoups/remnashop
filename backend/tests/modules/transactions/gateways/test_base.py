import pathlib
from decimal import Decimal
from typing import Optional

import pytest

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookAck,
    WebhookRequest,
    WebhookSignal,
    amount_to_float,
)
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY
from tests.modules.transactions.gateways.support import (
    ORDER_REF,
    RETURN_URL,
    WEBHOOK_URL,
    make_order,
)

_SIGNAL = WebhookSignal(reference=ORDER_REF, claims_paid=True)


class _Gateway(PaymentGateway):
    currency = Currency.RUB

    def __init__(self, payment: Optional[ProviderPayment]) -> None:
        super().__init__(settings={}, webhook_url=WEBHOOK_URL, return_url=RETURN_URL)
        self._payment = payment

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        raise NotImplementedError

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        return None

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        assert self._payment is not None
        return self._payment


def _paid(**overrides: object) -> ProviderPayment:
    values: dict[str, object] = {"paid": True, "amount": Decimal("500"), "reference": ORDER_REF}
    values.update(overrides)
    return ProviderPayment(**values)  # type: ignore[arg-type]


def test_amount_to_float_rounds_to_two_places() -> None:
    assert amount_to_float(Decimal("19.999")) == 20.0


def test_payment_gateway_is_abstract() -> None:
    with pytest.raises(TypeError):
        PaymentGateway(settings={}, webhook_url="x", return_url="y")  # type: ignore[abstract]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://pay.example", "data:text/html,x"])
def test_payment_intent_rejects_non_https_confirmation_url(url: str) -> None:
    with pytest.raises(PaymentGatewayError):
        PaymentIntent(confirmation_url=url)


def test_dataclasses_are_frozen() -> None:
    intent = PaymentIntent(confirmation_url="https://pay", provider_payment_id="p1")
    with pytest.raises(Exception):
        intent.confirmation_url = "mutated"  # type: ignore[misc]
    assert _SIGNAL.provider_payment_id is None
    assert WebhookAck().body == ""
    assert WebhookRequest(body=b"{}", headers={}).body == b"{}"


async def test_confirm_accepts_a_paid_payment_matching_the_order() -> None:
    payment = _paid(currency="rub", reference=ORDER_REF)
    assert await _Gateway(payment).confirm(make_order(), _SIGNAL) is payment


async def test_confirm_accepts_overpayment_and_missing_optional_fields() -> None:
    assert await _Gateway(_paid(amount=Decimal("501"))).confirm(make_order(), _SIGNAL)
    assert await _Gateway(_paid(amount=None)).confirm(make_order(), _SIGNAL)


@pytest.mark.parametrize(
    "payment",
    [
        ProviderPayment(paid=False, amount=Decimal("500"), reference=ORDER_REF),
        _paid(amount=Decimal("499.99")),
        _paid(currency="USD"),
        _paid(reference="someone-else"),
        _paid(reference=""),
    ],
)
async def test_confirm_rejects(payment: ProviderPayment) -> None:
    assert await _Gateway(payment).confirm(make_order(), _SIGNAL) is None


def test_every_registered_gateway_implements_the_full_contract() -> None:
    for gateway_class in GATEWAY_REGISTRY.values():
        assert gateway_class.__abstractmethods__ == frozenset(), gateway_class.__name__


def test_fetch_payment_is_abstract() -> None:
    assert "fetch_payment" in PaymentGateway.__abstractmethods__


def test_webhook_ack_defaults_to_the_class_ack() -> None:
    assert _Gateway(None).webhook_ack(None) == WebhookAck()


def test_gateways_package_imports_no_web_framework() -> None:
    package = pathlib.Path(__file__).parents[4] / "app" / "modules" / "payments" / "gateways"
    offenders = []
    for path in package.glob("*.py"):
        text = path.read_text()
        for banned in ("fastapi", "aiogram"):
            if f"import {banned}" in text or f"from {banned}" in text:
                offenders.append(f"{path.name}: {banned}")
    assert offenders == [], offenders
