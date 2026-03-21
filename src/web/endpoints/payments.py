from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status
from loguru import logger

from src.application.common import EventPublisher
from src.application.events import ErrorEvent
from src.application.use_cases.gateways.queries.providers import GetPaymentGatewayInstance
from src.core.config.app import AppConfig
from src.core.constants import API_V1, PAYMENTS_WEBHOOK_PATH
from src.core.enums import PaymentGatewayType
from src.infrastructure.taskiq.tasks.payments import handle_payment_transaction_task

router = APIRouter(prefix=API_V1 + PAYMENTS_WEBHOOK_PATH)


@router.post("/{gateway_type}")
@inject
async def payments_webhook(
    gateway_type: str,
    request: Request,
    config: FromDishka[AppConfig],
    event_publisher: FromDishka[EventPublisher],
    get_payment_gateway_instance: FromDishka[GetPaymentGatewayInstance],
) -> Response:
    try:
        gateway_enum = PaymentGatewayType(gateway_type.upper())
    except ValueError:
        logger.exception(f"Invalid gateway type received: '{gateway_type}'")
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    try:
        gateway = await get_payment_gateway_instance.system(gateway_enum)

        if not gateway.data.is_active:
            logger.warning(f"Webhook received for disabled payment gateway '{gateway_enum}'")
            return Response(status_code=status.HTTP_404_NOT_FOUND)

        if not gateway.data.settings.is_configured:  # type: ignore[union-attr]
            logger.warning(f"Webhook received for unconfigured payment gateway '{gateway_enum}'")
            return Response(status_code=status.HTTP_404_NOT_FOUND)

        payment_id, payment_status = await gateway.handle_webhook(request)
        await handle_payment_transaction_task.kiq(payment_id, payment_status)  # type: ignore[call-overload]
        return Response(status_code=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(f"Error processing webhook for '{gateway_type}': {e}")
        error_event = ErrorEvent(**config.build.data, exception=e)
        await event_publisher.publish(error_event)

    finally:
        if gateway is not None:
            return await gateway.build_webhook_response(request)
        return Response(status_code=status.HTTP_200_OK)
