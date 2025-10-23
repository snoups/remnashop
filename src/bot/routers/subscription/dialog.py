from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.kbd import Button, Column, Group, Row, Select, Start, SwitchTo, Url
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.states import Connect, MainMenu, Subscription
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.constants import PURCHASE_PREFIX
from src.core.enums import BannerName, PaymentGatewayType, PurchaseType

from .getters import (
    confirm_getter,
    duration_getter,
    payment_method_getter,
    plans_getter,
    subscription_getter,
    success_payment_getter,
)
from .handlers import (
    on_duration_select,
    on_get_subscription,
    on_payment_method_select,
    on_plan_select,
    on_subscription_plans,
)

subscription = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-main"),
    Row(
        Button(
            text=I18nFormat("btn-subscription-new"),
            id=f"{PURCHASE_PREFIX}{PurchaseType.NEW}",
            on_click=on_subscription_plans,
            when=~F["has_active_subscription"],
        ),
        Button(
            text=I18nFormat("btn-subscription-renew"),
            id=f"{PURCHASE_PREFIX}{PurchaseType.RENEW}",
            on_click=on_subscription_plans,
            when=F["has_active_subscription"],
        ),
        Button(
            text=I18nFormat("btn-subscription-change"),
            id=f"{PURCHASE_PREFIX}{PurchaseType.CHANGE}",
            on_click=on_subscription_plans,
            when=F["has_active_subscription"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-promocode"),
            id=f"{PURCHASE_PREFIX}promocode",
            state=Subscription.PROMOCODE,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-menu"),
            id="back",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.MAIN,
    getter=subscription_getter,
)

plans = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-plans"),
    Column(
        Select(
            text=I18nFormat("btn-subscription-plan", name=F["item"]["name"]),
            id=f"{PURCHASE_PREFIX}select_plan",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_plan_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id=f"{PURCHASE_PREFIX}back",
            state=Subscription.MAIN,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-menu"),
            id="back_menu",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.PLANS,
    getter=plans_getter,
)

duration = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-duration"),
    Group(
        Select(
            text=I18nFormat(
                "btn-subscription-duration",
                period=F["item"]["period"],
                price=F["item"]["price"],
                currency=F["item"]["currency"],
            ),
            id=f"{PURCHASE_PREFIX}select_duration",
            item_id_getter=lambda item: item["days"],
            items="durations",
            type_factory=int,
            on_click=on_duration_select,
        ),
        width=2,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-plans"),
            id=f"{PURCHASE_PREFIX}back_plans",
            state=Subscription.PLANS,
            when=~F["only_single_plan"],
        ),
        SwitchTo(
            text=I18nFormat("btn-back"),
            id=f"{PURCHASE_PREFIX}back_main",
            state=Subscription.MAIN,
            when=(F["only_single_plan"]) | (F["purchase_type"] == PurchaseType.RENEW),
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-menu"),
            id="back_menu",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.DURATION,
    getter=duration_getter,
)

payment_method = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-payment-method"),
    Column(
        Select(
            text=I18nFormat(
                "btn-subscription-payment-method",
                gateway_type=F["item"]["gateway_type"],
                price=F["item"]["price"],
                currency=F["item"]["currency"],
            ),
            id=f"{PURCHASE_PREFIX}select_payment_method",
            item_id_getter=lambda item: item["gateway_type"],
            items="payment_methods",
            type_factory=PaymentGatewayType,
            on_click=on_payment_method_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-duration"),
            id=f"{PURCHASE_PREFIX}back",
            state=Subscription.DURATION,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-menu"),
            id="back_menu",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.PAYMENT_METHOD,
    getter=payment_method_getter,
)

confirm = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-confirm"),
    Row(
        Url(
            text=I18nFormat("btn-subscription-pay"),
            url=Format("{url}"),
            when="url",
        ),
        Button(
            text=I18nFormat("btn-subscription-get"),
            id=f"{PURCHASE_PREFIX}get",
            on_click=on_get_subscription,
            when=~F["url"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-payment-method"),
            id=f"{PURCHASE_PREFIX}back_payment_method",
            state=Subscription.PAYMENT_METHOD,
            when=~F["only_single_gateway"],
        ),
        SwitchTo(
            text=I18nFormat("btn-subscription-back-duration"),
            id=f"{PURCHASE_PREFIX}back_duration",
            state=Subscription.DURATION,
            when=F["only_single_gateway"],
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-menu"),
            id="back_menu",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.CONFIRM,
    getter=confirm_getter,
)

success_payment = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-success"),
    Row(
        Start(
            text=I18nFormat("btn-subscription-connect"),
            id="connect",
            state=Connect.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-menu"),
            id="back_menu",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.SUCCESS,
    getter=success_payment_getter,
)

success_trial = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-trial"),
    Row(
        Start(
            text=I18nFormat("btn-subscription-connect"),
            id="connect",
            state=Connect.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-menu"),
            id="back_menu",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.TRIAL,
)

failed = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-failed"),
    Row(
        Start(
            text=I18nFormat("btn-back-menu"),
            id="back_menu",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.FAILED,
)

router = Dialog(
    subscription,
    plans,
    duration,
    payment_method,
    confirm,
    success_payment,
    success_trial,
    failed,
)
