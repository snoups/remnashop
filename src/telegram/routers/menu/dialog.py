from aiogram_dialog import Dialog, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    CopyText,
    Row,
    Start,
    SwitchInlineQueryChosenChatButton,
    SwitchTo,
    Url,
)
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.application.common.policy import Permission
from src.core.constants import INLINE_QUERY_INVITE, PAYMENT_PREFIX
from src.core.enums import BannerName
from src.telegram.keyboards import connect_buttons, custom_buttons
from src.telegram.routers.dashboard.users.handlers import on_user_search
from src.telegram.states import Dashboard, MainMenu, Subscription
from src.telegram.utils import require_permission
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate
from src.telegram.window import Window

from .getters import invite_about_getter, invite_getter, menu_getter
from .handlers import (
    on_get_trial,
    on_invite,
    on_show_qr,
    on_withdraw_points,
    show_reason,
)

menu = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-main-menu"),
    Row(
        *connect_buttons,
        Button(
            text=I18nFormat("btn-menu.connect-not-available"),
            id="not_available",
            on_click=show_reason,
            when=~F["connectable"],
        ),
        when=F["subscription_exists"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu.trial"),
            id="trial",
            on_click=on_get_trial,
            when=F["trial_available"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-menu.devices"),
            id="devices",
            state=MainMenu.DEVICES,
            when=F["devices_available"],
        ),
        Start(
            text=I18nFormat("btn-menu.subscription"),
            id=f"{PAYMENT_PREFIX}subscription",
            state=Subscription.MAIN,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu.invite"),
            id="invite",
            on_click=on_invite,
            when=F["referral_enabled"],
        ),
        SwitchInlineQueryChosenChatButton(
            text=I18nFormat("btn-menu.invite"),
            query=Format(INLINE_QUERY_INVITE),
            allow_user_chats=True,
            allow_group_chats=True,
            allow_channel_chats=True,
            id="send",
            when=~F["referral_enabled"],
        ),
        Url(
            text=I18nFormat("btn-menu.support"),
            id="support",
            url=Format("{support_url}"),
        ),
    ),
    *custom_buttons,
    Row(
        Start(
            text=I18nFormat("btn-menu.dashboard"),
            id="dashboard",
            state=Dashboard.MAIN,
            mode=StartMode.RESET_STACK,
            when=require_permission(Permission.VIEW_DASHBOARD),
        ),
    ),
    MessageInput(func=on_user_search),
    IgnoreUpdate(),
    state=MainMenu.MAIN,
    getter=menu_getter,
)


invite = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-invite"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-invite.about"),
            id="about",
            state=MainMenu.INVITE_ABOUT,
        ),
    ),
    Row(
        CopyText(
            text=I18nFormat("btn-invite.copy"),
            copy_text=Format("{referral_url}"),
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-invite.qr"),
            id="qr",
            on_click=on_show_qr,
        ),
        SwitchInlineQueryChosenChatButton(
            text=I18nFormat("btn-invite.send"),
            query=Format(INLINE_QUERY_INVITE),
            allow_user_chats=True,
            allow_group_chats=True,
            allow_channel_chats=True,
            id="send",
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-invite.withdraw-points"),
            id="withdraw_points",
            on_click=on_withdraw_points,
            when=~F["has_points"],
        ),
        Url(
            text=I18nFormat("btn-invite.withdraw-points"),
            id="withdraw_points",
            url=Format("{withdraw}"),
            when=F["has_points"],
        ),
        when=F["is_points_reward"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.INVITE,
    getter=invite_getter,
)

invite_about = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-invite-about"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=MainMenu.INVITE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.INVITE_ABOUT,
    getter=invite_about_getter,
)


router = Dialog(
    menu,
    invite,
    invite_about,
)
