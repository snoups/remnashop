from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, Start, SwitchTo
from magic_filter import F

from src.bot.keyboards import back_main_menu_button, main_menu_button
from src.bot.routers.extra.test import show_dev_popup
from src.bot.states import Dashboard, DashboardImporter
from src.bot.widgets.banner import Banner
from src.bot.widgets.i18n_format import I18nFormat
from src.bot.widgets.ignore_update import IgnoreUpdate
from src.core.enums import BannerName

from .getters import from_xui_getter, import_completed_getter, squads_getter, sync_completed_getter
from .handlers import (
    on_database_input,
    on_import_active_xui,
    on_import_all_xui,
    on_import_from_bot,
    on_squad_select,
    on_squads,
    on_sync,
)

importer = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-importer-from-xui"),
            id="xui",
            state=DashboardImporter.FROM_XUI,
        ),
        Button(
            text=I18nFormat("btn-importer-from-xui-shop"),
            id="xui_shop",
            on_click=on_import_from_bot,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-importer-sync"),
            id="sync",
            # on_click=on_sync,
            on_click=show_dev_popup,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=Dashboard.MAIN,
            mode=StartMode.RESET_STACK,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardImporter.MAIN,
)

from_xui = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-from-xui"),
    Row(
        Button(
            text=I18nFormat("btn-importer-squads"),
            id="squads",
            on_click=on_squads,
        ),
        when=F["has_exported"] & ~F["has_started"],
    ),
    Column(
        Button(
            text=I18nFormat("btn-importer-import-all"),
            id="import_all",
            on_click=on_import_all_xui,
        ),
        Button(
            text=I18nFormat("btn-importer-import-active"),
            id="import_active",
            on_click=on_import_active_xui,
        ),
        when=F["has_exported"] & ~F["has_started"],
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardImporter.MAIN,
            mode=StartMode.RESET_STACK,
        ),
        *main_menu_button,
    ),
    MessageInput(func=on_database_input),
    IgnoreUpdate(),
    state=DashboardImporter.FROM_XUI,
    getter=from_xui_getter,
)

import_completed = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-import-completed"),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardImporter.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=DashboardImporter.IMPORT_COMPLETED,
    getter=import_completed_getter,
)

squads = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-squads"),
    Column(
        Select(
            text=I18nFormat(
                "btn-squad-choice",
                name=F["item"]["name"],
                selected=F["item"]["selected"],
            ),
            id="select_squad",
            item_id_getter=lambda item: item["uuid"],
            items="squads",
            type_factory=str,
            on_click=on_squad_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardImporter.FROM_XUI,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardImporter.SQUADS,
    getter=squads_getter,
)

sync_completed = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-sync-completed"),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardImporter.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=DashboardImporter.SYNC_COMPLETED,
    getter=sync_completed_getter,
)

router = Dialog(
    importer,
    from_xui,
    squads,
    import_completed,
    sync_completed,
)
