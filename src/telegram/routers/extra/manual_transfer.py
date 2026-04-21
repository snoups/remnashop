from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject
from loguru import logger
from redis.asyncio import Redis

from src.application.common import Notifier
from src.application.common.dao import TransactionDao, UserDao
from src.application.dto import MessagePayloadDto, UserDto
from src.application.use_cases.gateways.commands.payment import ProcessPayment, ProcessPaymentDto
from src.core.enums import PaymentGatewayType, Role, TransactionStatus

router = Router(name=__name__)

MANUAL_TRANSFER_WAITING_KEY = "manual_transfer_waiting"


@router.message(F.photo | F.document)
@inject
async def on_manual_transfer_receipt(
    message: Message,
    user: UserDto,
    bot: Bot,
    transaction_dao: FromDishka[TransactionDao],
    user_dao: FromDishka[UserDao],
    notifier: FromDishka[Notifier],
    redis: FromDishka[Redis],
) -> None:
    waiting_payment_id = await _get_waiting_payment_id(redis, user.telegram_id)
    if not waiting_payment_id:
        return

    transaction = await transaction_dao.get_by_payment_id(waiting_payment_id)
    if not transaction or transaction.gateway_type != PaymentGatewayType.MANUAL_TRANSFER:
        return

    logger.info(f"{user.log} Received manual transfer receipt for payment '{waiting_payment_id}'")

    await _clear_waiting_payment_id(redis, user.telegram_id)

    admins = await user_dao.get_admins()
    for admin in admins:
        try:
            if message.photo:
                await bot.copy_message(
                    chat_id=admin.telegram_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=_build_admin_confirmation_keyboard(waiting_payment_id),
                )
            elif message.document:
                await bot.copy_message(
                    chat_id=admin.telegram_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=_build_admin_confirmation_keyboard(waiting_payment_id),
                )
        except Exception as e:
            logger.error(f"Failed to forward receipt to admin {admin.telegram_id}: {e}")

    await notifier.notify_user(
        user=user,
        payload=MessagePayloadDto(i18n_key="ntf-manual-transfer.receipt-received"),
    )


@router.callback_query(F.data.startswith("manual_transfer_confirm:"))
@inject
async def on_manual_transfer_confirm(
    callback: CallbackQuery,
    user: UserDto,
    process_payment: FromDishka[ProcessPayment],
) -> None:
    if user.role not in (Role.OWNER, Role.DEV, Role.ADMIN):
        await callback.answer("You are not authorized", show_alert=True)
        return

    payment_id_str = callback.data.replace("manual_transfer_confirm:", "")
    try:
        payment_id = UUID(payment_id_str)
    except ValueError:
        await callback.answer("Invalid payment ID", show_alert=True)
        return

    logger.info(f"{user.log} Confirming manual transfer for payment '{payment_id}'")

    await process_payment.system(
        ProcessPaymentDto(
            payment_id=payment_id,
            new_transaction_status=TransactionStatus.COMPLETED,
        )
    )

    await callback.message.edit_text(
        text=f"Payment '{payment_id_str}' confirmed ✓",
        reply_markup=None,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manual_transfer_reject:"))
@inject
async def on_manual_transfer_reject(
    callback: CallbackQuery,
    user: UserDto,
    process_payment: FromDishka[ProcessPayment],
) -> None:
    if user.role not in (Role.OWNER, Role.DEV, Role.ADMIN):
        await callback.answer("You are not authorized", show_alert=True)
        return

    payment_id_str = callback.data.replace("manual_transfer_reject:", "")
    try:
        payment_id = UUID(payment_id_str)
    except ValueError:
        await callback.answer("Invalid payment ID", show_alert=True)
        return

    logger.info(f"{user.log} Rejecting manual transfer for payment '{payment_id}'")

    await process_payment.system(
        ProcessPaymentDto(
            payment_id=payment_id,
            new_transaction_status=TransactionStatus.CANCELED,
        )
    )

    await callback.message.edit_text(
        text=f"Payment '{payment_id_str}' rejected ✗",
        reply_markup=None,
    )
    await callback.answer()


def _build_admin_confirmation_keyboard(payment_id: UUID) -> dict:
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(
        text="✓ Confirm",
        callback_data=f"manual_transfer_confirm:{payment_id}",
    )
    builder.button(
        text="✗ Reject",
        callback_data=f"manual_transfer_reject:{payment_id}",
    )
    return builder.as_markup()


async def _get_waiting_payment_id(redis: Redis, telegram_id: int) -> UUID | None:
    key = f"{MANUAL_TRANSFER_WAITING_KEY}:{telegram_id}"
    value = await redis.get(key)
    if value:
        return UUID(value)
    return None


async def _set_waiting_payment_id(redis: Redis, telegram_id: int, payment_id: UUID) -> None:
    key = f"{MANUAL_TRANSFER_WAITING_KEY}:{telegram_id}"
    await redis.set(key, str(payment_id), ex=3600)


async def _clear_waiting_payment_id(redis: Redis, telegram_id: int) -> None:
    key = f"{MANUAL_TRANSFER_WAITING_KEY}:{telegram_id}"
    await redis.delete(key)


async def set_manual_transfer_waiting(redis: Redis, telegram_id: int, payment_id: UUID) -> None:
    await _set_waiting_payment_id(redis, telegram_id, payment_id)