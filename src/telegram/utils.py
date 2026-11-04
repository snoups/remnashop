from datetime import datetime, timedelta
from typing import Callable, Optional

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common.when import Whenable

from src.application.common.policy import Permission, PermissionPolicy
from src.application.dto import TelegramUserDto
from src.core.constants import USER_KEY
from src.core.utils.time import datetime_now


def is_double_click(dialog_manager: DialogManager, key: str, cooldown: int = 10) -> bool:
    now = datetime_now()
    last_click_str: Optional[str] = dialog_manager.dialog_data.get(key)
    if last_click_str:
        last_click = datetime.fromisoformat(last_click_str.replace("Z", "+00:00"))
        if now - last_click < timedelta(seconds=cooldown):
            return True

    dialog_manager.dialog_data[key] = now.isoformat()
    return False


def require_permission(permission: Permission) -> Callable:
    def checker(
        data: dict,
        widget: Whenable,
        manager: DialogManager,
    ) -> bool:
        user: TelegramUserDto = manager.middleware_data[USER_KEY]
        return PermissionPolicy.has_permission(user, permission)

    return checker
