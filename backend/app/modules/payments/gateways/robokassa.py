import hashlib
from typing import Final, Optional
from urllib.parse import parse_qs, urlencode

from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import (
    PaymentGateway,
    PaymentIntent,
    WebhookRequest,
    WebhookResult,
)

_PAYMENT_URL: Final[str] = "https://auth.robokassa.ru/Merchant/Index.aspx"
_SHP_ORDER_ID: Final[str] = "Shp_order_id"


class RobokassaGateway(PaymentGateway):
    currency = Currency.RUB

    def __init__(self, *, settings: dict[str, str], webhook_url: str, return_url: str) -> None:
        super().__init__(settings=settings, webhook_url=webhook_url, return_url=return_url)
        self._last_inv_id: Optional[str] = None

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        out_sum = f"{order.final_price:.2f}"
        shp_params = {_SHP_ORDER_ID: order.idempotency_key}

        signature = self._hash(
            ":".join(
                [
                    self._settings["merchant_login"],
                    out_sum,
                    "0",
                    self._settings["password1"],
                    *(f"{key}={shp_params[key]}" for key in sorted(shp_params)),
                ]
            )
        )
        params = {
            "MerchantLogin": self._settings["merchant_login"],
            "OutSum": out_sum,
            "InvId": 0,
            "Description": f"Order #{order.id}",
            "SignatureValue": signature,
            "Culture": "ru",
            "Encoding": "utf-8",
            **shp_params,
        }
        return PaymentIntent(
            confirmation_url=f"{_PAYMENT_URL}?{urlencode(params)}", provider_payment_id=None
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookResult]:
        try:
            parsed = parse_qs(request.body.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError as error:
            raise PaymentGatewayError("Malformed Robokassa webhook") from error
        data = {key: values[0] for key, values in parsed.items()}

        received_sign = data.get("SignatureValue", "").upper()
        out_sum = data.get("OutSum", "")
        inv_id = data.get("InvId", "")
        self._last_inv_id = inv_id

        shp_params = {key: value for key, value in data.items() if key.startswith("Shp_")}
        order_ref = shp_params.get(_SHP_ORDER_ID)
        if not order_ref:
            raise PaymentGatewayError(f"Robokassa webhook missing '{_SHP_ORDER_ID}'")

        expected = self._hash(
            ":".join(
                [out_sum, inv_id, self._settings["password2"]]
                + [f"{key}={shp_params[key]}" for key in sorted(shp_params)]
            )
        )
        if expected != received_sign:
            raise PaymentGatewayError("Invalid Robokassa webhook signature")

        return WebhookResult(reference=order_ref, status=PaymentOrderStatus.PAID)

    def webhook_ack(self, result: Optional[WebhookResult]) -> str:
        return f"OK{self._last_inv_id or ''}"

    @staticmethod
    def _hash(raw: str) -> str:
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()
