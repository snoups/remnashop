from aiogram.enums import ParseMode
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Button, CopyText, ListGroup, SwitchTo
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from app.telegram.dialogs.keyboard import ConfigKeyboard
from app.telegram.routers.referrals.catalog import register_referrals_catalog
from app.telegram.routers.referrals.getters import (
    redeem_target_getter,
    referrals_about_getter,
    referrals_getter,
)
from app.telegram.routers.referrals.handlers import on_redeem_target_selected
from app.telegram.states import Referrals

register_referrals_catalog()

referrals_main = Window(
    DynamicMedia("banner", when="banner"),
    Format("{window_text}"),
    CopyText(Format("{copy_text}"), copy_text=Format("{referral_url}"), when=F["referral_url"]),
    ConfigKeyboard(window_key="referrals.main"),
    parse_mode=ParseMode.HTML,
    state=Referrals.MAIN,
    getter=referrals_getter,
)

redeem_target = Window(
    Format("{window_text}"),
    ListGroup(
        Button(text=Format("{item[label]}"), id="target", on_click=on_redeem_target_selected),
        id="targets",
        item_id_getter=lambda item: item["id"],
        items="subscriptions",
    ),
    SwitchTo(Format("{back_text}"), id="back", state=Referrals.MAIN),
    parse_mode=ParseMode.HTML,
    state=Referrals.REDEEM_TARGET,
    getter=redeem_target_getter,
)

referrals_about = Window(
    DynamicMedia("banner", when="banner"),
    Format("{window_text}"),
    ConfigKeyboard(window_key="referrals.about"),
    parse_mode=ParseMode.HTML,
    state=Referrals.ABOUT,
    getter=referrals_about_getter,
)

router = Dialog(referrals_main, redeem_target, referrals_about)
