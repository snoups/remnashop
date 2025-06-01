from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Row
from aiogram_dialog.widgets.text import Const

from app.bot.states import MenuState
from app.bot.widgets import Banner, I18NFormat, IgnoreInput
from app.core.enums import BannerName


async def getter(dialog_manager: DialogManager, **kwargs):
    return {
        "status": "active",
        "devices": 1,
        "max_devices": 3,
        "expiry_time": "3 дня",
    }


dialog = Dialog(
    Window(
        Banner(BannerName.MENU),
        I18NFormat("profile"),
        I18NFormat("space"),
        I18NFormat("subscription"),
        Row(Button(Const("✨ Попробовать бесплатно"), id="trial")),
        Row(
            Button(Const("💰 Баланс"), id="topup"),
            Button(Const("🛒 Подписка"), id="buy_sub"),
        ),
        Row(
            Button(Const("👥 Пригласить"), id="invite"),
            Button(Const("🆘 Помощь"), id="support"),
        ),
        Row(Button(Const("🎁 Активировать промокод"), id="activate_promo")),
        Row(Button(Const("🚀 Подключиться"), id="connect")),
        IgnoreInput(),
        state=MenuState.menu,
        getter=getter,
    )
)
