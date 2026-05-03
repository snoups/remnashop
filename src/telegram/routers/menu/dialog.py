from aiogram.enums import ButtonStyle
from aiogram_dialog import Dialog, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    ListGroup,
    Row,
    Start,
    SwitchTo,
)
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.application.common.policy import Permission
from src.core.constants import INLINE_QUERY_INVITE, PAYMENT_PREFIX
from src.core.enums import BannerName, PurchaseType
from src.telegram.keyboards import custom_buttons
from src.telegram.routers.dashboard.users.handlers import on_user_search
from src.telegram.states import Dashboard, MainMenu, Subscription
from src.telegram.utils import require_permission
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate
from src.telegram.widgets.icon_buttons import (
    IconButton,
    IconSwitchInlineQueryChosenChatButton,
    IconSwitchTo,
    IconUrl,
)
from src.telegram.widgets.icon_start import IconStart
from src.telegram.window import Window

from .getters import (
    device_confirm_delete_getter,
    devices_getter,
    invite_getter,
    menu_getter,
)
from .handlers import (
    on_device_delete_all_confirm,
    on_device_delete_confirm,
    on_device_delete_request,
    on_get_trial,
    on_invite,
    on_reissue_subscription_confirm,
)

INSTRUCTION_URL = "https://telegra.ph/Instrukciya-po-podklyucheniyu-nashego-VPN-05-02"

menu = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-main-menu"),
    Row(
        IconStart(
            text=I18nFormat("btn-subscription.new"),
            id=f"{PAYMENT_PREFIX}new",
            state=Subscription.PLANS,
            data={"purchase_type": PurchaseType.NEW},
            style=Style(ButtonStyle.PRIMARY),
            when=~F["has_active_subscription"],
            icon_custom_emoji_id="5258204546391351475",
        ),
        IconStart(
            text=I18nFormat("btn-subscription.new"),
            id=f"{PAYMENT_PREFIX}active",
            state=Subscription.MAIN,
            style=Style(ButtonStyle.PRIMARY),
            when=F["has_active_subscription"],
            icon_custom_emoji_id="5258204546391351475",
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu.trial"),
            id="trial",
            on_click=on_get_trial,
            when=F["trial_available"],
            style=Style(ButtonStyle.SUCCESS),
        ),
    ),
    Row(
        IconStart(
            text=I18nFormat("btn-menu.subscription"),
            id=f"{PAYMENT_PREFIX}subscription",
            state=Subscription.MAIN,
            icon_custom_emoji_id="5257969839313526622",
        ),
        IconUrl(
            text=I18nFormat("btn-menu.instruction"),
            id="instruction",
            url=Format(INSTRUCTION_URL),
            icon_custom_emoji_id="5258328383183396223",
        ),
    ),
    Row(
        IconSwitchTo(
            text=I18nFormat("btn-menu.support"),
            id="support",
            state=MainMenu.SUPPORT,
            icon_custom_emoji_id="5260249440450520061",
        ),
        IconButton(
            text=I18nFormat("btn-menu.invite"),
            id="invite",
            on_click=on_invite,
            when=F["referral_enabled"],
            icon_custom_emoji_id="5258362837411045098",
        ),
        IconSwitchInlineQueryChosenChatButton(
            text=I18nFormat("btn-menu.invite"),
            query=Format(INLINE_QUERY_INVITE),
            allow_user_chats=True,
            allow_group_chats=True,
            allow_channel_chats=True,
            id="send",
            when=~F["referral_enabled"],
            icon_custom_emoji_id="5258362837411045098",
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

devices = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-devices"),
    Row(
        Button(
            text=I18nFormat("btn-common.devices-empty"),
            id="devices_empty",
            when=~F["has_devices"],
        ),
    ),
    ListGroup(
        Row(
            Button(
                text=Format("{item[label]}"),
                id="device_item",
                on_click=on_device_delete_request,
            ),
        ),
        id="devices_list",
        item_id_getter=lambda item: item["short_hwid"],
        items="devices",
        when=F["has_devices"],
    ),
    Row(
        Start(
            text=I18nFormat("btn-devices.delete-all"),
            id="delete_all",
            state=MainMenu.DEVICE_CONFIRM_DELETE_ALL,
            when=F["has_devices"],
            style=Style(ButtonStyle.DANGER),
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-devices.reissue"),
            id="reissue",
            state=MainMenu.DEVICE_CONFIRM_REISSUE,
            style=Style(ButtonStyle.PRIMARY),
        ),
    ),
    Row(
        IconSwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=MainMenu.MAIN,
            icon_custom_emoji_id="5258236805890710909",
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.DEVICES,
    getter=devices_getter,
)

support = Window(
    Banner(BannerName.HELP),
    I18nFormat("msg-menu-support"),
    Row(
        IconUrl(
            text=I18nFormat("btn-support.user-agreement"),
            id="user_agreement",
            url=Format("{user_agreement_url}"),
            icon_custom_emoji_id="5257965810634202885",
        ),
    ),
    Row(
        IconUrl(
            text=I18nFormat("btn-support.privacy-policy"),
            id="privacy_policy",
            url=Format("{privacy_policy_url}"),
            icon_custom_emoji_id="5257965810634202885",
        ),
    ),
    Row(
        IconUrl(
            text=I18nFormat("btn-support.contact"),
            id="contact_support",
            url=Format("{support_url}"),
            icon_custom_emoji_id="5316727448644103237",
        ),
    ),
    Row(
        IconSwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=MainMenu.MAIN,
            icon_custom_emoji_id="5258236805890710909",
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.SUPPORT,
    getter=menu_getter,
)

device_confirm_delete = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-devices-confirm-delete"),
    Row(
        Button(
            text=I18nFormat("btn-devices.confirm-delete"),
            id="confirm_delete",
            on_click=on_device_delete_confirm,
            style=Style(ButtonStyle.DANGER),
        ),
        SwitchTo(
            text=I18nFormat("btn-common.cancel"),
            id="cancel",
            state=MainMenu.DEVICES,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.DEVICE_CONFIRM_DELETE,
    getter=device_confirm_delete_getter,
)

device_confirm_delete_all = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-devices-confirm-delete-all"),
    Row(
        Button(
            text=I18nFormat("btn-devices.confirm-delete"),
            id="confirm_delete_all",
            on_click=on_device_delete_all_confirm,
            style=Style(ButtonStyle.DANGER),
        ),
        SwitchTo(
            text=I18nFormat("btn-common.cancel"),
            id="cancel",
            state=MainMenu.DEVICES,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.DEVICE_CONFIRM_DELETE_ALL,
    getter=device_confirm_delete_getter,
)

invite = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-invite"),
    Row(
        IconUrl(
            text=I18nFormat("btn-invite.send"),
            id="send",
            url=Format("{share_url}"),
            icon_custom_emoji_id="5258362837411045098",
        ),
    ),
    Row(
        IconSwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=MainMenu.MAIN,
            icon_custom_emoji_id="5258236805890710909",
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.INVITE,
    getter=invite_getter,
)

device_confirm_reissue = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-devices-confirm-reissue"),
    Row(
        Button(
            text=I18nFormat("btn-devices.confirm-reissue"),
            id="confirm_reissue",
            on_click=on_reissue_subscription_confirm,
            style=Style(ButtonStyle.DANGER),
        ),
        SwitchTo(
            text=I18nFormat("btn-devices.cancel-reissue"),
            id="cancel_reissue",
            state=MainMenu.DEVICES,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.DEVICE_CONFIRM_REISSUE,
    getter=device_confirm_delete_getter,
)

router = Dialog(
    menu,
    devices,
    support,
    device_confirm_delete,
    device_confirm_delete_all,
    device_confirm_reissue,
    invite,
)
