from typing import Optional, Protocol, Union, runtime_checkable

from aiogram.types import Message

from src.application.dto import MessagePayloadDto, TempUserDto, UserDto
from src.core.enums import Role


@runtime_checkable
class Notifier(Protocol):
    async def notify_user(
        self,
        user: Union[TempUserDto, UserDto],
        payload: Optional[MessagePayloadDto] = None,
        i18n_key: Optional[str] = None,
    ) -> Optional[Message]: ...

    async def notify_admins(
        self,
        payload: MessagePayloadDto,
        roles: list[Role] = [Role.OWNER, Role.DEV, Role.ADMIN],
    ) -> None: ...

    async def delete_notification(self, chat_id: int, message_id: int) -> None: ...
