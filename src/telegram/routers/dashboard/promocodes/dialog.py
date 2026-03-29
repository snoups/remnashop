from aiogram.enums import ButtonStyle
from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, ListGroup, Row, Select, Start, SwitchTo
from aiogram_dialog.widgets.style import Style
from magic_filter import F

from src.core.enums import BannerName, PromocodeRewardType
from src.telegram.keyboards import main_menu_button
from src.telegram.states import Dashboard, DashboardPromocodes
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate

from .getters import configurator_getter, promocodes_getter, type_getter
from .handlers import (
    on_active_toggle,
    on_code_input,
    on_lifetime_input,
    on_max_activations_input,
    on_promocode_confirm,
    on_promocode_create,
    on_promocode_delete,
    on_promocode_select,
    on_reward_input,
    on_type_select,
)

promocodes = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat("msg-promocodes-main"),
    I18nFormat("msg-promocodes-empty", ~F["has_promocodes"]),
    Row(
        Button(
            text=I18nFormat("btn-promocodes.create"),
            id="create",
            on_click=on_promocode_create,
        ),
    ),
    ListGroup(
        Row(
            Button(
                text=I18nFormat(
                    "btn-promocodes.title",
                    code=F["item"]["code"],
                    is_active=F["item"]["is_active"],
                ),
                id="promocode_select",
                on_click=on_promocode_select,
            ),
        ),
        id="promocodes_list",
        item_id_getter=lambda item: item["id"],
        items="promocodes",
        when=F["has_promocodes"],
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
    getter=promocodes_getter,
)

configurator = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat("msg-promocode-configurator"),
    Row(
        Button(
            text=I18nFormat("btn-promocode.active", is_active=F["is_active"]),
            id="toggle_active",
            on_click=on_active_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocode.code"),
            id="code",
            state=DashboardPromocodes.CODE,
        ),
        SwitchTo(
            text=I18nFormat("btn-promocode.type"),
            id="type",
            state=DashboardPromocodes.TYPE,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocode.reward"),
            id="reward",
            state=DashboardPromocodes.REWARD,
        ),
        SwitchTo(
            text=I18nFormat("btn-promocode.lifetime"),
            id="lifetime",
            state=DashboardPromocodes.LIFETIME,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocode.max-activations"),
            id="max_activations",
            state=DashboardPromocodes.MAX_ACTIVATIONS,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-promocodes.create"),
            id="create_confirm",
            on_click=on_promocode_confirm,
            style=Style(ButtonStyle.SUCCESS),
        ),
        when=~F["is_edit"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-promocode.save"),
            id="save",
            on_click=on_promocode_confirm,
            style=Style(ButtonStyle.SUCCESS),
        ),
        Button(
            text=I18nFormat("btn-promocodes.delete"),
            id="delete",
            on_click=on_promocode_delete,
            style=Style(ButtonStyle.DANGER),
        ),
        when=F["is_edit"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.CONFIGURATOR,
    getter=configurator_getter,
)

code = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat("msg-promocode-code"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_code_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.CODE,
)

reward_type = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat("msg-promocode-type"),
    Column(
        Select(
            text=I18nFormat("promocode-type", promocode_type=F["item"]),
            id="type_select",
            item_id_getter=lambda item: item.value,
            items="types",
            type_factory=PromocodeRewardType,
            on_click=on_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.TYPE,
    getter=type_getter,
)

reward = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat("msg-promocode-reward"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_reward_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.REWARD,
)

lifetime = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat("msg-promocode-lifetime"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_lifetime_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.LIFETIME,
)

max_activations = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat("msg-promocode-max-activations"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_max_activations_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.MAX_ACTIVATIONS,
)

router = Dialog(
    promocodes,
    configurator,
    code,
    reward_type,
    reward,
    lifetime,
    max_activations,
)
