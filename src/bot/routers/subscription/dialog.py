from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.kbd import Button, Column, Group, Row, Select, Start, SwitchTo, Url
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.states import MainMenu, Subscription
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName, PaymentGatewayType

from .getters import (
    confirm_getter,
    duration_getter,
    payment_method_getter,
    plans_getter,
    subscription_getter,
)
from .handlers import (
    on_duration_selected,
    on_payment_method_selected,
    on_plan_selected,
    on_subscription_plans,
)

subscription = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-main"),
    Row(
        Button(
            text=I18nFormat("btn-subscription-purchase"),
            id="plans",
            on_click=on_subscription_plans,
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
            id="select_plan",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_plan_selected,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
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
            id="select_duration",
            item_id_getter=lambda item: item["days"],
            items="durations",
            type_factory=int,
            on_click=on_duration_selected,
        ),
        width=2,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-plans"),
            id="back",
            state=Subscription.PLANS,
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
            id="select_payment_method",
            item_id_getter=lambda item: item["gateway_type"],
            items="payment_methods",
            type_factory=PaymentGatewayType,
            on_click=on_payment_method_selected,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-duration"),
            id="back",
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
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-payment-method"),
            id="back",
            state=Subscription.PAYMENT_METHOD,
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

router = Dialog(
    subscription,
    plans,
    duration,
    payment_method,
    confirm,
)
