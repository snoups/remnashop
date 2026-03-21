from typing import Final, Optional

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_dialog import StartMode
from aiogram_dialog.widgets.kbd import CopyText, Group, ListGroup, Row, Start, Url, WebApp
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.core.constants import GOTO_PREFIX, PAYMENT_PREFIX, REPOSITORY, T_ME
from src.core.enums import ButtonType, PurchaseType
from src.telegram.states import DashboardUser, MainMenu, Subscription
from src.telegram.widgets import I18nFormat

CALLBACK_CHANNEL_CONFIRM: Final[str] = "channel_confirm"
CALLBACK_RULES_ACCEPT: Final[str] = "rules_accept"


def build_buttons_row(row: int) -> Group:
    return Group(
        ListGroup(
            Url(
                text=Format("{item.text}"),
                url=Format("{item.payload}"),
                when=F["item"].type == ButtonType.URL,
            ),
            CopyText(
                text=Format("{item.text}"),
                copy_text=Format("{item.payload}"),
                when=F["item"].type == ButtonType.COPY,
            ),
            WebApp(
                text=Format("{item.text}"),
                url=Format("{item.payload}"),
                when=F["item"].type == ButtonType.WEB_APP,
            ),
            id=f"custom_buttons_row_{row}",
            items=f"row_{row}_buttons",
            item_id_getter=lambda item: item.index,
        ),
        width=2,
    )


custom_buttons = (
    build_buttons_row(1),
    build_buttons_row(2),
    build_buttons_row(3),
)


connect_buttons = (
    WebApp(
        text=I18nFormat("btn-menu.connect"),
        url=Format("{connection_url}"),
        id="connect_miniapp",
        when=F["is_mini_app"] & F["connectable"],
        style=Style(ButtonStyle.PRIMARY),
    ),
    Url(
        text=I18nFormat("btn-menu.connect"),
        url=Format("{connection_url}"),
        id="connect_sub_page",
        when=~F["is_mini_app"] & F["connectable"],
        style=Style(ButtonStyle.PRIMARY),
    ),
)

main_menu_button = (
    Start(
        text=I18nFormat("btn-back.menu"),
        id="back_main_menu",
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
    ),
)

back_main_menu_button = (
    Row(
        Start(
            text=I18nFormat("btn-back.menu-return"),
            id="back_main_menu",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
)


def get_goto_buttons(support_url: str, is_referral_enable: bool) -> list[InlineKeyboardButton]:
    buttons = [
        InlineKeyboardButton(
            text="btn-goto.contact-support",
            url=support_url,
        ),
        InlineKeyboardButton(
            text="btn-goto.subscription",
            callback_data=f"{GOTO_PREFIX}{Subscription.MAIN.state}",
        ),
        InlineKeyboardButton(
            text="btn-goto.promocode",
            callback_data=f"{GOTO_PREFIX}{Subscription.PROMOCODE.state}",
        ),
    ]

    if is_referral_enable:
        buttons.append(
            InlineKeyboardButton(
                text="btn-goto.invite",
                callback_data=f"{GOTO_PREFIX}{MainMenu.INVITE.state}",
            )
        )

    return buttons


def get_renew_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="btn-goto.subscription-renew",
            callback_data=f"{GOTO_PREFIX}{PAYMENT_PREFIX}{PurchaseType.RENEW}",
        ),
    )
    return builder.as_markup()


def get_buy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="btn-goto.subscription",
            callback_data=f"{GOTO_PREFIX}{PAYMENT_PREFIX}{PurchaseType.NEW}",
        ),
    )
    return builder.as_markup()


def get_channel_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="btn-requirement.channel-join",
            url=channel_url,
            style=ButtonStyle.PRIMARY,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="btn-requirement.channel-confirm",
            callback_data=CALLBACK_CHANNEL_CONFIRM,
            style=ButtonStyle.SUCCESS,
        ),
    )
    return builder.as_markup()


def get_rules_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="btn-requirement.rules-accept",
            callback_data=CALLBACK_RULES_ACCEPT,
            style=ButtonStyle.SUCCESS,
        ),
    )
    return builder.as_markup()


def get_contact_support_keyboard(support_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="btn-goto.contact-support", url=support_url))
    return builder.as_markup()


def get_remnashop_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="btn-remnashop-info.github", url=REPOSITORY),
        InlineKeyboardButton(text="btn-remnashop-info.telegram", url=f"{T_ME}remna_shop"),
    )

    builder.row(
        InlineKeyboardButton(
            text="btn-remnashop-info.donate",
            url="https://boosty.to/snoups",
        )
    )

    return builder.as_markup()


def get_remnashop_update_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="btn-remnashop-info.release-latest",
            url=f"{REPOSITORY}/releases/latest",
            style=ButtonStyle.PRIMARY,
        ),
        InlineKeyboardButton(
            text="btn-remnashop-info.how-upgrade",
            url=f"{REPOSITORY}?tab=readme-ov-file#step-5--how-to-upgrade",
            style=ButtonStyle.PRIMARY,
        ),
    )

    return builder.as_markup()


def get_user_keyboard(
    telegram_id: int,
    referrer_telegram_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="btn-goto.user-profile",
            callback_data=f"{GOTO_PREFIX}{DashboardUser.MAIN.state}:{telegram_id}",
        ),
    )

    if referrer_telegram_id:
        builder.row(
            InlineKeyboardButton(
                text="btn-goto.referrer-profile",
                callback_data=f"{GOTO_PREFIX}{DashboardUser.MAIN.state}:{referrer_telegram_id}",
            ),
        )

    return builder.as_markup()


def get_boosty_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="⚡ BOOSTY",
            url="https://boosty.to/snoups",
        ),
    )

    return builder.as_markup()
