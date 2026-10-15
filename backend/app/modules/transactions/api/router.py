from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status

from app.api.errors import ApiError, error_responses
from app.core.constants import MAX_WEBHOOK_BODY_BYTES, PAYMENTS_WEBHOOK_PATH
from app.core.enums import PaymentGatewayType
from app.core.error_codes import ErrorCode
from app.core.exceptions import PaymentGatewayError, ValidationError
from app.core.utils.http import read_bounded_body, resolve_client_ip
from app.modules.transactions.dto import HandleWebhookDto
from app.modules.transactions.gateways.base import WebhookRequest
from app.modules.transactions.usecases import HandlePaymentWebhookUseCase

router = APIRouter(tags=["transactions"])


@router.post(PAYMENTS_WEBHOOK_PATH + "/{gateway_type}", responses=error_responses(403, 404, 502))
@inject
async def receive_payment_webhook(
    gateway_type: str,
    request: Request,
    use_case: FromDishka[HandlePaymentWebhookUseCase],
) -> Response:
    try:
        parsed_type = PaymentGatewayType(gateway_type.upper())
    except ValueError:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            f"Unknown payment gateway '{gateway_type}'",
            code=ErrorCode.GATEWAY_NOT_SUPPORTED,
        ) from None

    webhook_request = WebhookRequest(
        body=await read_bounded_body(request, MAX_WEBHOOK_BODY_BYTES),
        headers={key.lower(): value for key, value in request.headers.items()},
        client_ip=resolve_client_ip(request),
    )
    try:
        ack = await use_case.system(
            HandleWebhookDto(gateway_type=parsed_type, request=webhook_request)
        )
    except ValidationError as error:
        raise ApiError(status.HTTP_404_NOT_FOUND, str(error), code=error.code) from None
    except PaymentGatewayError as error:
        raise ApiError(
            status.HTTP_502_BAD_GATEWAY,
            "Could not verify payment",
            code=ErrorCode.PAYMENT_GATEWAY_ERROR,
        ) from error
    return Response(content=ack.body, media_type=ack.media_type, status_code=status.HTTP_200_OK)
