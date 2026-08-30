from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import Message


class PrivateFilter(BaseFilter):
    async def __call__(self, event: Message) -> bool:
        return event.chat.type == ChatType.PRIVATE
