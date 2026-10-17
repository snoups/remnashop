import json
from datetime import timedelta
from decimal import Decimal
from typing import Any, Callable, Final, Optional, Union

import httpx

from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import PaymentHttpClient
from tests.modules.subscriptions.factories import make_plan_snapshot

WEBHOOK_URL: Final[str] = "https://shop.example/api/v1/payments/test"
RETURN_URL: Final[str] = "https://shop.example"
ORDER_REF: Final[str] = "order-key-1"

Responder = Callable[[httpx.Request], httpx.Response]


def _no_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected provider call: {request.method} {request.url}")


# for a gateway exercised without any provider call
NO_HTTP: Final[PaymentHttpClient] = PaymentHttpClient(
    httpx.AsyncClient(transport=httpx.MockTransport(_no_network))
)


def make_order(**overrides: Any) -> TransactionDto:
    defaults: dict[str, Any] = {
        "id": 42,
        "user_id": 7,
        "plan_id": 1,
        "plan_snapshot": make_plan_snapshot(plan_id=1),
        "duration_days": 30,
        "currency": Currency.RUB,
        "purchase_type": PurchaseType.NEW,
        "gateway_type": PaymentGatewayType.YOOKASSA,
        "status": TransactionStatus.PENDING,
        "base_price": Decimal("500"),
        "discount_percent": 0,
        "discount_source": DiscountSource.NONE,
        "final_price": Decimal("500"),
        "anchor_base_price": Decimal("500"),
        "anchor_final_price": Decimal("500"),
        "idempotency_key": ORDER_REF,
        "expires_at": datetime_now() + timedelta(minutes=30),
    }
    defaults.update(overrides)
    return TransactionDto(**defaults)


def webhook(
    body: Union[bytes, dict[str, Any]], headers: Optional[dict[str, str]] = None
) -> WebhookRequest:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    lowered = {key.lower(): value for key, value in (headers or {}).items()}
    return WebhookRequest(body=raw, headers=lowered)


class HttpRecorder:
    def __init__(self, respond: Responder) -> None:
        self.requests: list[httpx.Request] = []
        self._respond = respond
        self.client = PaymentHttpClient(httpx.AsyncClient(transport=httpx.MockTransport(self)))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._respond(request)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_json(self) -> Any:
        return json.loads(self.last.content)


def json_response(payload: Any, status_code: int = 200) -> Responder:
    return lambda request: httpx.Response(status_code, json=payload)
