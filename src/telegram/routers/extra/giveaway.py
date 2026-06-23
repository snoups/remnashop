from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka
from loguru import logger

from src.application.common import Notifier
from src.application.dto import MessagePayloadDto, UserDto
from src.application.use_cases.giveaway.commands import (
    SaveGiveawayPhone,
    SaveGiveawayPhoneDto,
)
from src.telegram.states import GiveawayPhone

router = Router(name=__name__)


@router.callback_query(F.data.startswith("giveaway_phone:"))
async def on_leave_phone(
    callback: CallbackQuery,
    state: FSMContext,
    user: UserDto,
    notifier: FromDishka[Notifier],
) -> None:
    try:
        entry_id = int((callback.data or "").split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        await callback.answer()
        return

    await state.set_state(GiveawayPhone.INPUT)
    await state.update_data(giveaway_entry_id=entry_id)
    await notifier.notify_user(
        user,
        payload=MessagePayloadDto(
            i18n_key="ntf-giveaway.phone-request",
            delete_after=None,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "giveaway_skip")
async def on_skip_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.message(GiveawayPhone.INPUT)
async def on_phone_input(
    message: Message,
    state: FSMContext,
    user: UserDto,
    notifier: FromDishka[Notifier],
    save_phone: FromDishka[SaveGiveawayPhone],
) -> None:
    phone = (message.text or "").strip()
    if not phone.isdigit() or not 10 <= len(phone) <= 15:
        await notifier.notify_user(
            user,
            payload=MessagePayloadDto(
                i18n_key="ntf-giveaway.phone-invalid",
                delete_after=None,
            ),
        )
        return

    data = await state.get_data()
    entry_id = data.get("giveaway_entry_id")
    if not isinstance(entry_id, int):
        await state.clear()
        await notifier.notify_user(user, i18n_key="ntf-error.unknown")
        return

    try:
        await save_phone(
            user,
            SaveGiveawayPhoneDto(
                entry_id=entry_id,
                user_telegram_id=user.telegram_id,
                phone=phone,
            ),
        )
    except Exception:
        logger.exception(f"{user.log} Failed to save giveaway phone for entry '{entry_id}'")
        await notifier.notify_user(user, i18n_key="ntf-error.unknown")
        return

    await state.clear()
    await notifier.notify_user(user, i18n_key="ntf-giveaway.phone-saved")
