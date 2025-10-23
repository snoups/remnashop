from aiogram import Bot
from aiogram_dialog import BgManagerFactory, ShowMode, StartMode
from dishka import FromDishka
from dishka.integrations.taskiq import inject

from src.bot.states import MainMenu, Subscription
from src.core.enums import PurchaseType
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.broker import broker


@broker.task
@inject
async def redirect_to_main_menu_task(
    user: UserDto,
    bot: FromDishka[Bot],
    bg_manager_factory: FromDishka[BgManagerFactory],
) -> None:
    bg_manager = bg_manager_factory.bg(
        bot=bot,
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
    )
    await bg_manager.start(
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@broker.task
@inject
async def redirect_to_successed_trial_task(
    user: UserDto,
    bot: FromDishka[Bot],
    bg_manager_factory: FromDishka[BgManagerFactory],
) -> None:
    bg_manager = bg_manager_factory.bg(
        bot=bot,
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
    )
    await bg_manager.start(
        state=Subscription.TRIAL,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@broker.task
@inject
async def redirect_to_successed_payment_task(
    user: UserDto,
    purchase_type: PurchaseType,
    bot: FromDishka[Bot],
    bg_manager_factory: FromDishka[BgManagerFactory],
) -> None:
    bg_manager = bg_manager_factory.bg(
        bot=bot,
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
    )
    await bg_manager.start(
        state=Subscription.SUCCESS,
        data={"purchase_type": purchase_type},
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@broker.task
@inject
async def redirect_to_failed_subscription_task(
    user: UserDto,
    bot: FromDishka[Bot],
    bg_manager_factory: FromDishka[BgManagerFactory],
) -> None:
    bg_manager = bg_manager_factory.bg(
        bot=bot,
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
    )
    await bg_manager.start(
        state=Subscription.FAILED,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
