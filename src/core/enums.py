from enum import Enum, StrEnum, auto
from typing import Union

from aiogram.types import BotCommand


class UpperStrEnum(StrEnum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name


class UserRoleHierarchy(Enum):
    DEV = 3
    ADMIN = 2
    USER = 1


class UserRole(UpperStrEnum):
    DEV = auto()
    ADMIN = auto()
    USER = auto()

    def __le__(self, other: Union["UserRole", str]) -> bool:
        if isinstance(other, UserRole):
            other_name = other.name
        elif isinstance(other, str):
            other_name = other
        else:
            raise TypeError(f"Cannot compare UserRole with '{type(other)}'")
        return UserRoleHierarchy[self.name].value <= UserRoleHierarchy[other_name].value

    def __lt__(self, other: Union["UserRole", str]) -> bool:
        if isinstance(other, UserRole):
            other_name = other.name
        elif isinstance(other, str):
            other_name = other
        else:
            raise TypeError(f"Cannot compare UserRole with '{type(other)}'")
        return UserRoleHierarchy[self.name].value < UserRoleHierarchy[other_name].value


class Command(Enum):
    START = BotCommand(command="start", description="cmd-start")
    PAYSUPPORT = BotCommand(command="paysupport", description="cmd-paysupport")
    HELP = BotCommand(command="help", description="cmd-help")


class Locale(StrEnum):
    AR = auto()  # Arabic
    AZ = auto()  # Azerbaijani
    BE = auto()  # Belarusian
    CS = auto()  # Czech
    DE = auto()  # German
    EN = auto()  # English
    ES = auto()  # Spanish
    FA = auto()  # Persian
    FR = auto()  # French
    HE = auto()  # Hebrew
    HI = auto()  # Hindi
    ID = auto()  # Indonesian
    IT = auto()  # Italian
    JA = auto()  # Japanese
    KK = auto()  # Kazakh
    KO = auto()  # Korean
    MS = auto()  # Malay
    NL = auto()  # Dutch
    PL = auto()  # Polish
    PT = auto()  # Portuguese
    RO = auto()  # Romanian
    RU = auto()  # Russian
    SR = auto()  # Serbian
    TR = auto()  # Turkish
    UK = auto()  # Ukrainian
    UZ = auto()  # Uzbek
    VI = auto()  # Vietnamese


# https://docs.aiogram.dev/en/latest/api/types/update.html
class MiddlewareEventType(StrEnum):
    AIOGD_UPDATE = auto()  # AIOGRAM DIALOGS
    UPDATE = auto()
    MESSAGE = auto()
    EDITED_MESSAGE = auto()
    CHANNEL_POST = auto()
    EDITED_CHANNEL_POST = auto()
    BUSINESS_CONNECTION = auto()
    BUSINESS_MESSAGE = auto()
    EDITED_BUSINESS_MESSAGE = auto()
    DELETED_BUSINESS_MESSAGES = auto()
    MESSAGE_REACTION = auto()
    MESSAGE_REACTION_COUNT = auto()
    INLINE_QUERY = auto()
    CHOSEN_INLINE_RESULT = auto()
    CALLBACK_QUERY = auto()
    SHIPPING_QUERY = auto()
    PRE_CHECKOUT_QUERY = auto()
    PURCHASED_PAID_MEDIA = auto()
    POLL = auto()
    POLL_ANSWER = auto()
    MY_CHAT_MEMBER = auto()
    CHAT_MEMBER = auto()
    CHAT_JOIN_REQUEST = auto()
    CHAT_BOOST = auto()
    REMOVED_CHAT_BOOST = auto()
    ERROR = auto()
