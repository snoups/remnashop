from typing import Any, Optional

from dishka.integrations.taskiq import FromDishka, inject

from app.core.broker import broker
from app.modules.customer_notifications.dto import (
    NotifyCustomerDto,
    SendCustomerTelegramDto,
    ShowPaymentCanceledDto,
)
from app.modules.customer_notifications.usecases import (
    NotifyCustomerUseCase,
    SendCustomerTelegramUseCase,
    ShowPaymentCanceledUseCase,
)


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def notify_customer_task(
    user_id: int,
    event_type: str,
    outbox_id: int,
    args: dict[str, Any],
    use_case: FromDishka[NotifyCustomerUseCase],
    # defaulted: messages queued before the field existed still deserialize
    payment_key: Optional[str] = None,
    subscription_id: Optional[int] = None,
) -> None:
    await use_case.system(
        NotifyCustomerDto(
            user_id=user_id,
            event_type=event_type,
            outbox_id=outbox_id,
            args=args,
            payment_key=payment_key,
            subscription_id=subscription_id,
        )
    )


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def send_customer_telegram_task(
    user_id: int,
    text: str,
    use_case: FromDishka[SendCustomerTelegramUseCase],
    buttons: Optional[list[dict[str, str]]] = None,
) -> None:
    await use_case.system(
        SendCustomerTelegramDto(user_id=user_id, text=text, buttons=buttons or [])
    )


# best effort: a missed cancel window leaves the bot on the payment screen, nothing more
@broker.task
@inject(patch_module=True)
async def show_payment_canceled_task(
    order_id: int, use_case: FromDishka[ShowPaymentCanceledUseCase]
) -> None:
    await use_case.system(ShowPaymentCanceledDto(order_id=order_id))
