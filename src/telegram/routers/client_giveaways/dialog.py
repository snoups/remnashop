from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, ListGroup, Row, Start, SwitchTo
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.core.enums import BannerName
from src.telegram.states import ClientGiveaways, MainMenu
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate

from .getters import (
    client_giveaway_conditions_getter,
    client_giveaway_getter,
    client_giveaway_results_getter,
    client_giveaways_getter,
)
from .handlers import (
    on_buy_for_giveaway,
    on_client_campaign_select,
    on_client_phone_input,
    on_client_phone_request,
)

giveaways = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-client-giveaways"),
    I18nFormat("msg-client-giveaways-empty", when=~F["has_giveaways"]),
    ListGroup(
        Button(
            text=Format("🎁 {item[name]}"),
            id="campaign",
            on_click=on_client_campaign_select,
        ),
        id="campaigns",
        item_id_getter=lambda item: item["id"],
        items="giveaways",
        when=F["has_giveaways"],
    ),
    Row(
        Start(
            text=I18nFormat("btn-back.menu"),
            id="back",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        )
    ),
    IgnoreUpdate(),
    getter=client_giveaways_getter,
    state=ClientGiveaways.LIST,
)

view = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-client-giveaway-view"),
    Row(
        Button(
            text=I18nFormat("btn-client-giveaway.buy"),
            id="buy",
            on_click=on_buy_for_giveaway,
            when=F["can_buy"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-client-giveaway.conditions"),
            id="conditions",
            state=ClientGiveaways.CONDITIONS,
        ),
        Button(
            text=I18nFormat("btn-client-giveaway.phone"),
            id="phone",
            on_click=on_client_phone_request,
            when=F["can_edit_phone"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-client-giveaway.results"),
            id="results",
            state=ClientGiveaways.RESULTS,
            when=F["show_results"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=ClientGiveaways.LIST,
        ),
    ),
    IgnoreUpdate(),
    getter=client_giveaway_getter,
    state=ClientGiveaways.VIEW,
)

conditions = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-client-giveaway-conditions"),
    Format("{conditions}"),
    SwitchTo(
        text=I18nFormat("btn-back.general"),
        id="back",
        state=ClientGiveaways.VIEW,
    ),
    IgnoreUpdate(),
    getter=client_giveaway_conditions_getter,
    state=ClientGiveaways.CONDITIONS,
)

phone = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-client-giveaway-phone"),
    MessageInput(func=on_client_phone_input),
    SwitchTo(
        text=I18nFormat("btn-back.general"),
        id="back",
        state=ClientGiveaways.VIEW,
    ),
    IgnoreUpdate(),
    getter=client_giveaway_getter,
    state=ClientGiveaways.PHONE,
)

results = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-client-giveaway-results"),
    Format("{results}"),
    SwitchTo(
        text=I18nFormat("btn-back.general"),
        id="back",
        state=ClientGiveaways.VIEW,
    ),
    IgnoreUpdate(),
    getter=client_giveaway_results_getter,
    state=ClientGiveaways.RESULTS,
)

router = Dialog(giveaways, view, conditions, phone, results)
