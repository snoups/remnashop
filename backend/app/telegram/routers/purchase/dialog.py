from typing import Any, Optional

from aiogram.enums import ButtonStyle, ParseMode
from aiogram_dialog import Dialog, DialogManager, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, ListGroup, Row, Start, SwitchTo, Url
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.style import BaseStyle, Style
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from app.core.enums import PlanBadge
from app.telegram.banners import with_window_banner
from app.telegram.routers.purchase.catalog import register_purchase_catalog
from app.telegram.routers.purchase.getters import (
    confirm_getter,
    duration_getter,
    email_getter,
    link_choice_getter,
    method_getter,
    pay_getter,
    plan_getter,
    recurring_terms_getter,
)
from app.telegram.routers.purchase.handlers import (
    on_confirm,
    on_confirm_back,
    on_duration_back,
    on_duration_selected,
    on_email_input,
    on_link_new,
    on_link_renew,
    on_method_selected,
    on_plan_selected,
    on_purchase_start,
    on_recurring_choice,
)
from app.telegram.states import MainMenu, Purchase

register_purchase_catalog()


class _ItemIcon(BaseStyle):
    """A list button's custom emoji icon, from its item's `icon_id`."""

    async def _render_style(self, data: dict[str, Any], manager: DialogManager) -> None:
        return None

    async def _render_emoji(self, data: dict[str, Any], manager: DialogManager) -> Optional[str]:
        icon_id: Optional[str] = data["item"].get("icon_id")
        return icon_id


# the purchase steps carry the banner of the subscriptions window they start from
_BANNER_WINDOW = "subscriptions.list"

plan = Window(
    DynamicMedia("banner", when="banner"),
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
            | Style(style=ButtonStyle.SUCCESS, when=F["item"]["badge"] == PlanBadge.POPULAR.value)
            | _ItemIcon(),
        ),
        id="plans",
        item_id_getter=lambda item: item["id"],
        items="plans",
    ),
    Cancel(Format("{back_text}")),
    parse_mode=ParseMode.HTML,
    state=Purchase.PLAN,
    getter=with_window_banner(_BANNER_WINDOW, plan_getter),
)

duration = Window(
    DynamicMedia("banner", when="banner"),
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
    getter=with_window_banner(_BANNER_WINDOW, duration_getter),
)

method = Window(
    DynamicMedia("banner", when="banner"),
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
    getter=with_window_banner(_BANNER_WINDOW, method_getter),
)

email = Window(
    DynamicMedia("banner", when="banner"),
    Format("{window_text}"),
    MessageInput(on_email_input),
    Button(Format("{back_text}"), id="back", on_click=on_confirm_back),
    parse_mode=ParseMode.HTML,
    state=Purchase.EMAIL,
    getter=with_window_banner(_BANNER_WINDOW, email_getter),
)

confirm = Window(
    DynamicMedia("banner", when="banner"),
    Format("{window_text}"),
    Row(
        Button(Format("{pay_text}"), id="pay", on_click=on_confirm, when="can_pay"),
        Button(Format("{back_text}"), id="back", on_click=on_confirm_back),
    ),
    ListGroup(
        Button(
            Format("{recurring_on_text}"),
            id="recurring_on",
            on_click=on_recurring_choice,
            when="recurring_on",
        ),
        Button(
            Format("{recurring_off_text}"),
            id="recurring_off",
            on_click=on_recurring_choice,
            when="recurring_off",
        ),
        id="recurring_choice",
        item_id_getter=lambda item: item["id"],
        items="recurring_choices",
    ),
    SwitchTo(
        Format("{recurring_terms_text}"),
        id="recurring_terms",
        state=Purchase.RECURRING_TERMS,
        when="recurring_terms",
    ),
    parse_mode=ParseMode.HTML,
    state=Purchase.CONFIRM,
    getter=with_window_banner(_BANNER_WINDOW, confirm_getter),
)

# Keep the full terms independent of Telegram's media-caption limit.
recurring_terms = Window(
    Format("{window_text}"),
    SwitchTo(Format("{back_text}"), id="back", state=Purchase.CONFIRM),
    parse_mode=ParseMode.HTML,
    state=Purchase.RECURRING_TERMS,
    getter=recurring_terms_getter,
)

pay = Window(
    DynamicMedia("banner", when="banner"),
    Format("{window_text}"),
    Url(Format("{pay_text}"), Format("{payment_url}")),
    Start(Format("{menu_text}"), id="menu", state=MainMenu.MAIN, mode=StartMode.RESET_STACK),
    parse_mode=ParseMode.HTML,
    state=Purchase.PAY,
    getter=with_window_banner(_BANNER_WINDOW, pay_getter),
)

link_choice = Window(
    DynamicMedia("banner", when="banner"),
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
    getter=with_window_banner(_BANNER_WINDOW, link_choice_getter),
)

router = Dialog(
    plan,
    duration,
    method,
    email,
    confirm,
    recurring_terms,
    pay,
    link_choice,
    on_start=on_purchase_start,
)
