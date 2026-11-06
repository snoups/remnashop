import io

import segno
from aiogram import Bot
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Keyboard
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.constants import USER_KEY
from app.core.exceptions import CooldownError, NotFoundError, ValidationError
from app.modules.referrals import (
    MAX_BONUS_DAYS,
    GetOwnReferralStatsUseCase,
    ListBonusDaysTargetsUseCase,
    RedeemBonusDaysDto,
    RedeemBonusDaysUseCase,
    ResetOwnReferralCodeUseCase,
)
from app.modules.users import UserDto
from app.telegram.i18n import format_datetime, get_translator
from app.telegram.routers.referrals.getters import referral_url
from app.telegram.states import Referrals


@inject
async def on_referral_qr(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    get_own_referral_stats: FromDishka[GetOwnReferralStatsUseCase],
    bot: FromDishka[Bot],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    stats = await get_own_referral_stats(user)
    me = await bot.me()
    if stats.referral_code and me.username and isinstance(callback.message, Message):
        image = io.BytesIO()
        segno.make(referral_url(me.username, stats.referral_code), error="m").save(
            image, kind="png", scale=10, border=2
        )
        await callback.message.answer_photo(
            BufferedInputFile(image.getvalue(), filename="referral-qr.png")
        )
    await callback.answer()


@inject
async def on_reset_referral_code(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    reset_own_referral_code: FromDishka[ResetOwnReferralCodeUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    try:
        await reset_own_referral_code(user)
    except CooldownError as error:
        await callback.answer(
            runner.get(
                "ntf-common.cooldown-active", available_at=format_datetime(error.available_at)
            ),
            show_alert=True,
        )
        return
    except ValidationError:
        await callback.answer(runner.get("ntf-referrals.reset-disabled"), show_alert=True)
        return
    await callback.answer(runner.get("ntf-referrals.code-reset"), show_alert=True)


async def _redeem(
    callback: CallbackQuery,
    dialog_manager: DialogManager,
    redeem_bonus_days: RedeemBonusDaysUseCase,
    i18n: TranslatorHub,
    subscription_id: int,
) -> None:
    # the middleware loads the user on every update, so this balance is current
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    # one renewal takes at most MAX_BONUS_DAYS, the rest stays on the balance
    days = min(user.bonus_days, MAX_BONUS_DAYS)
    # a button left on an old screen; the usecase would renew by zero days
    if days <= 0:
        await callback.answer(runner.get("ntf-referrals.redeem-failed"), show_alert=True)
        return
    try:
        await redeem_bonus_days(
            user, RedeemBonusDaysDto(subscription_id=subscription_id, days=days)
        )
    except (NotFoundError, ValidationError):
        await callback.answer(runner.get("ntf-referrals.redeem-failed"), show_alert=True)
        return
    await callback.answer(runner.get("ntf-referrals.days-redeemed", days=days))
    await dialog_manager.switch_to(Referrals.MAIN)


@inject
async def on_redeem_days(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    redeem_bonus_days: FromDishka[RedeemBonusDaysUseCase],
    list_bonus_days_targets: FromDishka[ListBonusDaysTargetsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    # what the days can extend: no trial, no disabled one, none whose traffic never comes back
    targets = await list_bonus_days_targets(user)
    if not targets:
        runner = get_translator(i18n, user)
        await callback.answer(runner.get("ntf-referrals.no-subscription"), show_alert=True)
    elif len(targets) == 1:
        await _redeem(callback, dialog_manager, redeem_bonus_days, i18n, targets[0].id)
    else:
        await dialog_manager.switch_to(Referrals.REDEEM_TARGET)


@inject
async def on_redeem_target_selected(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    redeem_bonus_days: FromDishka[RedeemBonusDaysUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    subscription_id = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    await _redeem(callback, dialog_manager, redeem_bonus_days, i18n, subscription_id)
