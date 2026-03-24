from typing import TYPE_CHECKING, Annotated, Any, List, NewType, TypeAlias, Union

from aiogram.types import (
    ForceReply,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from pydantic import PlainValidator
from remnapy.models import UserResponseDto
from remnapy.models.webhook import UserDto as UserWebhookDto

from src.core.enums import Locale, SystemNotificationType, UserNotificationType

if TYPE_CHECKING:
    ListStr: TypeAlias = list[str]
    ListLocale: TypeAlias = list[Locale]
else:
    ListStr = NewType("ListStr", list[str])
    ListLocale = NewType("ListLocale", list[Locale])

AnyKeyboard: TypeAlias = Union[
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ForceReply,
]


NotificationType: TypeAlias = Union[SystemNotificationType, UserNotificationType]

RemnaUserDto: TypeAlias = Union[UserWebhookDto, UserResponseDto]

StringList: TypeAlias = Annotated[
    ListStr, PlainValidator(lambda x: [s.strip() for s in x.split(",")])
]


def _validate_locale_list(x: Any) -> List[Locale]:
    if isinstance(x, list):
        return [v if isinstance(v, Locale) else Locale(str(v).strip()) for v in x]

    if isinstance(x, str):
        if not x.strip():
            return []
        return [Locale(loc.strip()) for loc in x.split(",")]

    raise ValueError(f"Expected list or str, got {type(x)}")


LocaleList: TypeAlias = Annotated[
    List[Locale],
    PlainValidator(_validate_locale_list),
]
