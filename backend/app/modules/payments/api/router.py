import orjson
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.exceptions import PaymentGatewayError
from app.modules.payments.usecases import HandleYooKassaWebhookUseCase

router = APIRouter(tags=["payments"])


@router.post("/payments/webhooks/yookassa")
@inject
async def receive_yookassa_webhook(
    request: Request,
    use_case: FromDishka[HandleYooKassaWebhookUseCase],
) -> Response:
    try:
        body = orjson.loads(await request.body())
    except orjson.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook"
        ) from None
    webhook_object = body.get("object") if isinstance(body, dict) else None
    external_payment_id = webhook_object.get("id") if isinstance(webhook_object, dict) else None
    if not external_payment_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook")

    try:
        await use_case.system(external_payment_id)
    except PaymentGatewayError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not verify payment"
        ) from error
    return Response(status_code=status.HTTP_200_OK)
