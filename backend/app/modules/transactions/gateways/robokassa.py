from typing import Final, Optional
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from app.core.enums import Currency
from app.core.exceptions import PaymentGatewayError
from app.modules.transactions.dto import TransactionDto, WebhookRequest
from app.modules.transactions.gateways.base import (
    NOT_PAID,
    PaymentGateway,
    PaymentIntent,
    ProviderPayment,
    WebhookAck,
    WebhookSignal,
)
from app.modules.transactions.gateways.common import (
    PROVIDER_API_TIMEOUT_S,
    format_moscow,
    md5_hex,
    parse_form,
    safe_equals,
    to_decimal,
)

_PAYMENT_URL: Final[str] = "https://auth.robokassa.ru/Merchant/Index.aspx"
_OP_STATE_URL: Final[str] = "https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpStateExt"
_NAMESPACES: Final[dict[str, str]] = {"r": "http://merchant.roboxchange.com/WebService/"}
_SHP_ORDER_ID: Final[str] = "Shp_order_id"
_RESULT_OK: Final[str] = "0"
_RESULT_NOT_FOUND: Final[str] = "3"
_STATE_PAID: Final[str] = "100"


# Docs: https://docs.robokassa.ru/ru/pay-interface
class RobokassaGateway(PaymentGateway):
    currency = Currency.RUB

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        login = self._require("merchant_login")
        out_sum = f"{order.final_price:.2f}"
        inv_id = str(order.id)
        shp_params = {_SHP_ORDER_ID: order.idempotency_key}
        signature = md5_hex(
            ":".join(
                [
                    login,
                    out_sum,
                    inv_id,
                    self._require("password1"),
                    *(f"{key}={shp_params[key]}" for key in sorted(shp_params)),
                ]
            )
        )
        params = {
            "MerchantLogin": login,
            "OutSum": out_sum,
            "InvId": inv_id,
            "Description": f"Order #{order.id}",
            "SignatureValue": signature,
            "Culture": "ru",
            "Encoding": "utf-8",
            # Docs give no zone; Moscow time never shortens the link either way.
            "ExpirationDate": format_moscow(order.expires_at),
            **shp_params,
        }
        return PaymentIntent(
            confirmation_url=f"{_PAYMENT_URL}?{urlencode(params)}", provider_payment_id=inv_id
        )

    async def parse_webhook(self, request: WebhookRequest) -> Optional[WebhookSignal]:
        data = parse_form(request.body, "Robokassa")
        out_sum = data.get("OutSum", "")
        inv_id = data.get("InvId", "")
        shp_params = {key: value for key, value in data.items() if key.startswith("Shp_")}
        order_ref = shp_params.get(_SHP_ORDER_ID)
        if not order_ref:
            raise PaymentGatewayError(f"Robokassa webhook missing '{_SHP_ORDER_ID}'")

        expected = md5_hex(
            ":".join(
                [out_sum, inv_id, self._require("password2")]
                + [f"{key}={shp_params[key]}" for key in sorted(shp_params)]
            )
        )
        if not safe_equals(expected, data.get("SignatureValue", ""), ignore_case=True):
            raise PaymentGatewayError("Invalid Robokassa webhook signature")

        # ResultURL is only called for successful payments.
        return WebhookSignal(
            reference=order_ref,
            claims_paid=True,
            provider_payment_id=inv_id or None,
            amount=to_decimal(out_sum),
        )

    def webhook_ack(self, signal: Optional[WebhookSignal]) -> WebhookAck:
        inv_id = signal.provider_payment_id if signal is not None else None
        return WebhookAck(body=f"OK{inv_id or ''}")

    async def fetch_payment(self, order: TransactionDto, signal: WebhookSignal) -> ProviderPayment:
        if signal.amount is None:
            return NOT_PAID
        login = self._require("merchant_login")
        inv_id = str(order.id)
        response = await self._http.get(
            _OP_STATE_URL,
            params={
                "MerchantLogin": login,
                "InvoiceID": inv_id,
                "Signature": md5_hex(f"{login}:{inv_id}:{self._require('password2')}"),
            },
            timeout=PROVIDER_API_TIMEOUT_S,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        result_code = root.findtext("r:Result/r:Code", namespaces=_NAMESPACES)
        if result_code == _RESULT_NOT_FOUND:
            return NOT_PAID
        if result_code != _RESULT_OK:
            raise PaymentGatewayError(f"Robokassa OpStateExt error code {result_code}")
        state_code = root.findtext("r:State/r:Code", namespaces=_NAMESPACES)
        # Shp_ names are case-insensitive on Robokassa's side (docs show `shp_interface`)
        order_ref = next(
            (
                field.findtext("r:Value", default="", namespaces=_NAMESPACES)
                for field in root.iterfind("r:UserFields/r:Field", _NAMESPACES)
                if (field.findtext("r:Name", default="", namespaces=_NAMESPACES)).lower()
                == _SHP_ORDER_ID.lower()
            ),
            "",
        )
        return ProviderPayment(
            paid=state_code == _STATE_PAID,
            amount=signal.amount,
            reference=order_ref,
            provider_payment_id=inv_id,
        )
