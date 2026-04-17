from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, Start, SwitchTo
from magic_filter import F

from src.core.enums import BannerName
from src.telegram.keyboards import back_main_menu_button, main_menu_button
from src.telegram.states import Dashboard, DashboardImporter
from src.telegram.widgets.banner import Banner
from src.telegram.widgets.i18n_format import I18nFormat
from src.telegram.widgets.ignore_update import IgnoreUpdate

from .getters import (
    from_xui_getter,
    import_completed_getter,
    squads_getter,
    sync_bot_completed_getter,
    sync_panel_completed_getter,
)
from .handlers import (
    on_database_input,
    on_import_active_xui,
    on_import_all_xui,
    on_squad_select,
    on_squads,
    on_sync_from_bot,
    on_sync_from_panel,
)

importer = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-importer.from-xui"),
            id="xui",
            state=DashboardImporter.FROM_XUI,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-importer.sync-from-panel"),
            id="sync_panel",
            state=DashboardImporter.SYNC_PANEL,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-importer.sync-from-bot"),
            id="sync_bot",
            state=DashboardImporter.SYNC_BOT,
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
    state=DashboardImporter.MAIN,
)

sync_panel = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-sync-panel"),
    Row(
        Button(
            text=I18nFormat("btn-importer.sync-start"),
            id="sync_panel_start",
            on_click=on_sync_from_panel,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardImporter.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardImporter.SYNC_PANEL,
)

sync_bot = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-sync-bot"),
    Row(
        Button(
            text=I18nFormat("btn-importer.sync-start"),
            id="sync_bot_start",
            on_click=on_sync_from_bot,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardImporter.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardImporter.SYNC_BOT,
)

from_xui = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-from-xui"),
    Row(
        Button(
            text=I18nFormat("btn-importer.squads"),
            id="squads",
            on_click=on_squads,
        ),
        when=F["has_exported"] & ~F["has_started"],
    ),
    Column(
        Button(
            text=I18nFormat("btn-importer.import-all"),
            id="import_all",
            on_click=on_import_all_xui,
        ),
        Button(
            text=I18nFormat("btn-importer.import-active"),
            id="import_active",
            on_click=on_import_active_xui,
        ),
        when=F["has_exported"] & ~F["has_started"],
    ),
    Row(
        Start(
            text=I18nFormat("btn-back.general"),
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
            text=I18nFormat("btn-back.general"),
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
                "btn-common.squad-choice",
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
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardImporter.FROM_XUI,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardImporter.SQUADS,
    getter=squads_getter,
)

sync_panel_completed = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-sync-panel-completed"),
    Row(
        Start(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardImporter.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=DashboardImporter.SYNC_PANEL_COMPLETED,
    getter=sync_panel_completed_getter,
)

sync_bot_completed = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-importer-sync-bot-completed"),
    Row(
        Start(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardImporter.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=DashboardImporter.SYNC_BOT_COMPLETED,
    getter=sync_bot_completed_getter,
)

router = Dialog(
    importer,
    sync_panel,
    sync_bot,
    from_xui,
    squads,
    import_completed,
    sync_panel_completed,
    sync_bot_completed,
)
