from typing import Any

from dishka.integrations.taskiq import FromDishka, inject

from app.core.broker import broker
from app.modules.customer_notifications.dto import NotifyCustomerDto, SendCustomerTelegramDto
from app.modules.customer_notifications.usecases import (
    NotifyCustomerUseCase,
    SendCustomerTelegramUseCase,
)


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def notify_customer_task(
    user_id: int,
    event_type: str,
    outbox_id: int,
    args: dict[str, Any],
    use_case: FromDishka[NotifyCustomerUseCase],
) -> None:
    await use_case.system(
        NotifyCustomerDto(user_id=user_id, event_type=event_type, outbox_id=outbox_id, args=args)
    )


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def send_customer_telegram_task(
    user_id: int, text: str, use_case: FromDishka[SendCustomerTelegramUseCase]
) -> None:
    await use_case.system(SendCustomerTelegramDto(user_id=user_id, text=text))
