from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status
from loguru import logger

from src.core.constants import API_V1, PAYMENTS_WEBHOOK_PATH
from src.core.enums import PaymentGatewayType
from src.infrastructure.taskiq.tasks.payments import handle_payment_transaction_task
from src.services.payment_gateway import PaymentGatewayService

router = APIRouter(prefix=API_V1 + PAYMENTS_WEBHOOK_PATH)


@router.post("/{gateway_type}")
@inject
async def generic_webhook(
    gateway_type: str,
    request: Request,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> Response:
    try:
        gateway_enum = PaymentGatewayType(gateway_type.upper())
        gateway = await payment_gateway_service._get_gateway_instance(gateway_enum)

        payment_id, payment_status = await gateway.handle_webhook(request)
        await handle_payment_transaction_task.kiq(payment_id, payment_status)
        return Response(status_code=status.HTTP_200_OK)

    except ValueError:
        logger.error(f"Invalid gateway type received: {gateway_type}")
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    except Exception as exception:
        logger.error(f"Error processing webhook for {gateway_type}: {exception}")
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
