import traceback
from typing import cast

from aiogram.utils.formatting import Text
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Request, Response, status
from loguru import logger
from remnapy.controllers import WebhookUtility
from remnapy.models.webhook import NodeDto, UserDto, UserHwidDeviceEventDto

from src.core.config import AppConfig
from src.core.constants import API_V1, REMNAWAVE_WEBHOOK_PATH
from src.core.utils.message_payload import MessagePayload
from src.services.notification import NotificationService
from src.services.remnawave import RemnawaveService

router = APIRouter(prefix=API_V1)


@router.post(REMNAWAVE_WEBHOOK_PATH)
@inject
async def remnawave_webhook(
    request: Request,
    config: FromDishka[AppConfig],
    remnawave_service: FromDishka[RemnawaveService],
    notification_service: FromDishka[NotificationService],
) -> Response:
    try:
        raw_body = await request.body()
        data = await request.json()
        logger.debug(f"Received Remnawave webhook payload: '{data}'")
        payload = WebhookUtility.parse_webhook(
            body=raw_body.decode("utf-8"),
            headers=dict(request.headers),
            webhook_secret=config.remnawave.webhook_secret.get_secret_value(),
            validate=True,
        )
    except Exception as exception:
        logger.exception(f"Webhook validation failed with error '{exception}'")
        raise HTTPException(status_code=401)

    if not payload:
        logger.warning("Payload is empty after validation")
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        if WebhookUtility.is_user_event(payload.event):
            user = cast(UserDto, WebhookUtility.get_typed_data(payload))
            await remnawave_service.handle_user_event(payload.event, user)

        elif WebhookUtility.is_user_hwid_devices_event(payload.event):
            event = cast(UserHwidDeviceEventDto, WebhookUtility.get_typed_data(payload))
            await remnawave_service.handle_device_event(
                payload.event,
                event.user,
                event.hwid_user_device,
            )

        elif WebhookUtility.is_node_event(payload.event):
            node = cast(NodeDto, WebhookUtility.get_typed_data(payload))
            await remnawave_service.handle_node_event(payload.event, node)

        else:
            logger.warning(f"Unhandled Remnawave event type '{payload.event}'")

    except Exception as exception:
        logger.exception(f"Failed to process Remnawave webhook due to '{exception}'")
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await notification_service.error_notify(
            traceback_str=traceback_str,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    "user": False,
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
            ),
        )

    return Response(status_code=status.HTTP_200_OK)
