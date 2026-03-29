from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.application.dto import MessagePayloadDto, UserDto
from src.core.types import NotificationType
from src.core.utils.time import datetime_now


@dataclass(frozen=True, kw_only=True)
class BaseEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime_now)

    notification_type: NotificationType = field(init=False)

    @property
    def event_type(self) -> str:
        return self.__class__.__name__

    @property
    def event_key(self) -> str:
        return f"event-{self.notification_type.value.lower().replace('_', '-')}"

    def as_payload(self, *args: Any, **kwargs: Any) -> "MessagePayloadDto":
        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs=asdict(self),
            disable_default_markup=False,
            delete_after=None,
        )


@dataclass(frozen=True, kw_only=True)
class SystemEvent(BaseEvent): ...


@dataclass(frozen=True, kw_only=True)
class UserEvent(BaseEvent):
    user: UserDto
