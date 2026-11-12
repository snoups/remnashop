import calendar
from datetime import datetime, time, timedelta
from typing import Optional

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Keyboard
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub
from loguru import logger
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import TIMEZONE, USER_KEY
from app.core.enums import PurchaseType
from app.core.exceptions import NotFoundError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.subscriptions import (
    ActivateTrialSubscriptionUseCase,
    GetAvailableTrialUseCase,
    ListOwnActiveSubscriptionsUseCase,
    ListOwnSubscriptionsUseCase,
)
from app.modules.users import UserDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.i18n import format_wait, get_translator
from app.telegram.notice import answer_notice
from app.telegram.routers.menu.getters import connect_problem, menu_subscription
from app.telegram.routers.purchase.handlers import PLAN_CODE_KEY
from app.telegram.states import MainMenu, Purchase, Subscriptions

router = Router(name=__name__)


@router.message(CommandStart())
async def on_start_command(message: Message, user: UserDto, dialog_manager: DialogManager) -> None:
    logger.info(f"{user.log} Started menu dialog")
    await dialog_manager.start(
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(Command("paysupport"))
async def on_paysupport_command(
    message: Message, user: UserDto, i18n: FromDishka[TranslatorHub]
) -> None:
    logger.info(f"{user.log} Called '/paysupport' command")
    await message.answer(get_translator(i18n, user).get("msg-paysupport"))


@inject
async def on_get_trial(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    activate_trial_subscription: FromDishka[ActivateTrialSubscriptionUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    result = await get_available_trial(user)

    if result.plan is None or not result.is_trial_available:
        await answer_notice(callback, runner.get("ntf-common.trial-unavailable"))
        return

    if not result.is_free:
        # a paid trial is bought like any plan, opened the way a plan link opens it
        await dialog_manager.start(
            Purchase.PLAN,
            data={"purchase_type": PurchaseType.NEW.value, PLAN_CODE_KEY: result.plan.public_code},
        )
        return

    try:
        subscription = await activate_trial_subscription(user)
    except (NotFoundError, ValidationError):
        logger.exception(f"{user.log} Trial activation failed")
        await answer_notice(callback, runner.get("ntf-common.trial-unavailable"))
        return

    await answer_notice(callback, runner.get("ntf-common.trial-activated"))
    # its card, where "Connect" is, whatever the menu shows
    await dialog_manager.start(
        Subscriptions.CARD,
        data={SELECTED_SUBSCRIPTION_KEY: subscription.id},
        mode=StartMode.RESET_STACK,
    )


def next_traffic_reset(
    strategy: TrafficLimitStrategy, created_at: Optional[datetime], now: datetime
) -> Optional[datetime]:
    midnight = datetime.combine(now.date(), time(), tzinfo=TIMEZONE)
    if strategy is TrafficLimitStrategy.DAY:
        return midnight + timedelta(days=1)
    if strategy is TrafficLimitStrategy.WEEK:
        return midnight + timedelta(days=7 - now.weekday())
    if strategy is TrafficLimitStrategy.MONTH:
        year, month = divmod(now.year * 12 + now.month, 12)
        return midnight.replace(year=year, month=month + 1, day=1)
    if strategy is TrafficLimitStrategy.MONTH_ROLLING and created_at is not None:
        # on the day of the month the subscription was created, the month's last day if shorter
        year, month = now.year, now.month
        for _ in range(2):
            day = min(created_at.day, calendar.monthrange(year, month)[1])
            reset = midnight.replace(year=year, month=month, day=day)
            if reset > now:
                return reset
            year, month = divmod(year * 12 + month, 12)
            month += 1
    return None


@inject
async def on_show_connect_problem(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    active = await list_own_active_subscriptions(user)
    subscription = menu_subscription(
        active[0] if active else None, await list_own_subscriptions(user)
    )
    problem = connect_problem(subscription)
    if subscription is None or not problem:
        # working again since the menu was drawn: redrawn with "Connect"
        await dialog_manager.show()
        return
    runner = get_translator(i18n, user)
    reset = next_traffic_reset(
        subscription.traffic_limit_strategy, subscription.created_at, datetime_now()
    )
    text = runner.get(
        "ntf-common.connect-not-available",
        status=problem,
        is_trial=int(subscription.is_trial),
        reset_in=format_wait(runner, reset) if reset is not None else "none",
    )
    await callback.answer(text, show_alert=True)
