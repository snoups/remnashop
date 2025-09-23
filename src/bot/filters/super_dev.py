from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message

from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY, USER_KEY
from src.infrastructure.database.models.dto import UserDto


class SuperDevFilter(BaseFilter):
    async def __call__(self, event: Message, **data: Any) -> bool:
        config: AppConfig = data[CONFIG_KEY]
        user: UserDto = data[USER_KEY]
        return user.telegram_id == config.bot.dev_id
