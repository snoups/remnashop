from aiogram_dialog import Dialog, ShowMode, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Row, SwitchTo, Start
from aiogram_dialog.widgets.style import Style
from aiogram.enums import ButtonStyle

from src.core.enums import BannerName
from src.telegram.states import DashboardRemnashop, RemnashopBackup
from src.telegram.widgets import Banner, I18nFormat, IgnoreUpdate

from .getters import backup_getter
from .handlers import (
    on_backup_assets,
    on_backup_database,
    on_interval_input,
    on_max_files_input,
    on_set_interval,
    on_set_max_files,
    on_toggle_enabled,
    on_toggle_send_to_chat,
)

main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-main"),
    Row(
        Button(
            text=I18nFormat("btn-backup.toggle-enabled"),
            id="toggle_enabled",
            on_click=on_toggle_enabled,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-backup.set-interval"),
            id="set_interval",
            on_click=on_set_interval,
        ),
        Button(
            text=I18nFormat("btn-backup.set-max-files"),
            id="set_max_files",
            on_click=on_set_max_files,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-backup.toggle-send"),
            id="toggle_send",
            on_click=on_toggle_send_to_chat,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-backup.backup-assets"),
            id="backup_assets",
            on_click=on_backup_assets,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-backup.backup-db"),
            id="backup_db",
            on_click=on_backup_database,
            style=Style(ButtonStyle.PRIMARY),
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=DashboardRemnashop.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopBackup.MAIN,
    getter=backup_getter,
)

interval = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-set-interval"),
    MessageInput(func=on_interval_input),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=RemnashopBackup.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopBackup.INTERVAL,
    getter=backup_getter,
)

max_files = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-set-max-files"),
    MessageInput(func=on_max_files_input),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back.general"),
            id="back",
            state=RemnashopBackup.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopBackup.MAX_FILES,
    getter=backup_getter,
)

router = Dialog(main, interval, max_files)
