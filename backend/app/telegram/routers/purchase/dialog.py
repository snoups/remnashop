from aiogram.enums import ButtonStyle, ParseMode
from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.kbd import Button, Cancel, ListGroup, Row, Start, SwitchTo, Url
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from app.core.enums import PlanBadge
from app.telegram.routers.purchase.catalog import register_purchase_catalog
from app.telegram.routers.purchase.getters import (
    confirm_getter,
    duration_getter,
    link_choice_getter,
    method_getter,
    pay_getter,
    plan_getter,
)
from app.telegram.routers.purchase.handlers import (
    on_confirm,
    on_confirm_back,
    on_duration_back,
    on_duration_selected,
    on_link_new,
    on_link_renew,
    on_method_selected,
    on_plan_selected,
    on_purchase_start,
)
from app.telegram.states import MainMenu, Purchase

register_purchase_catalog()

plan = Window(
    Format("{window_text}"),
    ListGroup(
        Button(
            text=Format("{item[label]}"),
            id="plan",
            on_click=on_plan_selected,
            # a badged plan stands out: "best value" blue, "popular" green
            style=Style(
                style=ButtonStyle.PRIMARY, when=F["item"]["badge"] == PlanBadge.BEST_VALUE.value
            )
            | Style(style=ButtonStyle.SUCCESS, when=F["item"]["badge"] == PlanBadge.POPULAR.value),
        ),
        id="plans",
        item_id_getter=lambda item: item["id"],
        items="plans",
    ),
    Cancel(Format("{back_text}")),
    parse_mode=ParseMode.HTML,
    state=Purchase.PLAN,
    getter=plan_getter,
)

duration = Window(
    Format("{window_text}"),
    ListGroup(
        Button(text=Format("{item[label]}"), id="duration", on_click=on_duration_selected),
        id="durations",
        item_id_getter=lambda item: item["days"],
        items="durations",
    ),
    Button(Format("{back_text}"), id="back", on_click=on_duration_back),
    parse_mode=ParseMode.HTML,
    state=Purchase.DURATION,
    getter=duration_getter,
)

method = Window(
    Format("{window_text}"),
    ListGroup(
        Button(text=Format("{item[label]}"), id="method", on_click=on_method_selected),
        id="methods",
        item_id_getter=lambda item: item["id"],
        items="methods",
    ),
    SwitchTo(Format("{back_text}"), id="back", state=Purchase.DURATION),
    parse_mode=ParseMode.HTML,
    state=Purchase.METHOD,
    getter=method_getter,
)

confirm = Window(
    Format("{window_text}"),
    Row(
        Button(Format("{pay_text}"), id="pay", on_click=on_confirm),
        Button(Format("{back_text}"), id="back", on_click=on_confirm_back),
    ),
    parse_mode=ParseMode.HTML,
    state=Purchase.CONFIRM,
    getter=confirm_getter,
)

pay = Window(
    Format("{window_text}"),
    Url(Format("{pay_text}"), Format("{payment_url}")),
    Start(Format("{menu_text}"), id="menu", state=MainMenu.MAIN, mode=StartMode.RESET_STACK),
    parse_mode=ParseMode.HTML,
    state=Purchase.PAY,
    getter=pay_getter,
)

link_choice = Window(
    Format("{window_text}"),
    ListGroup(
        Button(text=Format("{item[label]}"), id="renew", on_click=on_link_renew),
        id="owned",
        item_id_getter=lambda item: item["id"],
        items="subscriptions",
    ),
    Button(Format("{new_text}"), id="new", on_click=on_link_new, when="has_plan"),
    Start(Format("{menu_text}"), id="menu", state=MainMenu.MAIN, mode=StartMode.RESET_STACK),
    parse_mode=ParseMode.HTML,
    state=Purchase.LINK_CHOICE,
    getter=link_choice_getter,
)

router = Dialog(plan, duration, method, confirm, pay, link_choice, on_start=on_purchase_start)
