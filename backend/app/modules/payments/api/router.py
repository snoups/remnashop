from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.enums import PaymentGatewayType
from app.core.exceptions import PaymentGatewayError, ValidationError
from app.core.utils.http import resolve_client_ip
from app.modules.payments.gateways.base import WebhookRequest
from app.modules.payments.usecases import HandlePaymentWebhookUseCase, HandleWebhookInput

router = APIRouter(tags=["payments"])


@router.post("/payments/{gateway_type}")
@inject
async def receive_payment_webhook(
    gateway_type: str,
    request: Request,
    use_case: FromDishka[HandlePaymentWebhookUseCase],
) -> Response:
    try:
        parsed_type = PaymentGatewayType(gateway_type.upper())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from None

    webhook_request = WebhookRequest(
        body=await request.body(),
        headers={key.lower(): value for key, value in request.headers.items()},
        query=dict(request.query_params),
        client_ip=resolve_client_ip(request),
    )
    try:
        ack = await use_case.system(
            HandleWebhookInput(gateway_type=parsed_type, request=webhook_request)
        )
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from None
    except PaymentGatewayError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not verify payment"
        ) from error
    return Response(content=ack or "", status_code=status.HTTP_200_OK)
