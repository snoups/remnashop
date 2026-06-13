from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, ListGroup, Row, Select, Start, SwitchTo
from magic_filter import F

from src.core.enums import BannerName, PromoAudience
from src.telegram.keyboards import main_menu_button
from src.telegram.states import Dashboard, DashboardPromocodes
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate

from .getters import audience_getter, configurator_getter, list_getter, plans_getter
from .handlers import (
    on_audience_select,
    on_code_input,
    on_confirm,
    on_create,
    on_deactivate,
    on_lifetime_input,
    on_max_activations_input,
    on_plan_select,
    on_promocode_select,
    on_reward_input,
)

promocodes_main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocodes-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocodes.list"),
            id="list",
            state=DashboardPromocodes.LIST,
        ),
        Button(
            text=I18nFormat("btn-promocodes.create"),
            id="create",
            on_click=on_create,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=Dashboard.MAIN,
            mode=StartMode.RESET_STACK,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.MAIN,
)

promocodes_list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocodes-list"),
    ListGroup(
        Row(
            Button(
                text=I18nFormat(
                    "btn-promocode.item",
                    is_active=F["item"]["is_active"],
                    code=F["item"]["code"],
                    discount_percent=F["item"]["discount_percent"],
                ),
                id="promocode_select",
                on_click=on_promocode_select,
            ),
        ),
        id="promocodes_list",
        item_id_getter=lambda item: item["id"],
        items="promocodes",
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.LIST,
    getter=list_getter,
)

configurator = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-configurator", when=~F["is_edit"]),
    I18nFormat("msg-promocode-view", when=F["is_edit"]),
    Row(
        Button(
            text=I18nFormat("btn-promocode.confirm"),
            id="confirm",
            on_click=on_confirm,
        ),
        when=~F["is_edit"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-promocode.deactivate"),
            id="deactivate",
            on_click=on_deactivate,
        ),
        when=F["is_edit"] & F["is_active"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back_to_lifetime",
            state=DashboardPromocodes.LIFETIME,
            when=~F["is_edit"],
        ),
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back_to_list",
            state=DashboardPromocodes.LIST,
            when=F["is_edit"],
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.CONFIGURATOR,
    getter=configurator_getter,
)

code_input = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-code"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.MAIN,
        ),
    ),
    MessageInput(func=on_code_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.CODE,
)

reward_input = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-reward"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.CODE,
        ),
    ),
    MessageInput(func=on_reward_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.REWARD,
)

allowed_plan = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-allowed"),
    Column(
        Select(
            text=I18nFormat("btn-promocode.plan-choice", name=F["item"]["name"]),
            id="plan_select",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_plan_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.REWARD,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.ALLOWED,
    getter=plans_getter,
)

audience = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-availability"),
    Column(
        Select(
            text=I18nFormat("btn-promocode.audience-choice", audience=F["item"]),
            id="audience_select",
            item_id_getter=lambda item: item.value,
            items="audiences",
            type_factory=PromoAudience,
            on_click=on_audience_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.ALLOWED,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.AVAILABILITY,
    getter=audience_getter,
)

max_activations = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-type"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.AVAILABILITY,
        ),
    ),
    MessageInput(func=on_max_activations_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.TYPE,
)

lifetime_input = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-lifetime"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.TYPE,
        ),
    ),
    MessageInput(func=on_lifetime_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.LIFETIME,
)

router = Dialog(
    promocodes_main,
    promocodes_list,
    configurator,
    code_input,
    reward_input,
    allowed_plan,
    audience,
    max_activations,
    lifetime_input,
)
