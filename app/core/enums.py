from enum import Enum, StrEnum, auto

from aiogram.types import BotCommand, ContentType


class BannerFormat(StrEnum):
    JPG = auto()
    JPEG = auto()
    PNG = auto()
    GIF = auto()
    WEBP = auto()  # TODO: check

    @property
    def content_type(self) -> ContentType:
        return {
            self.JPG: ContentType.PHOTO,
            self.JPEG: ContentType.PHOTO,
            self.PNG: ContentType.PHOTO,
            self.GIF: ContentType.ANIMATION,
            self.WEBP: ContentType.PHOTO,
        }[self]


class BannerName(StrEnum):
    DEFAULT = auto()
    MENU = auto()


class UserRole(StrEnum):
    ADMIN = auto()
    USER = auto()


class SubscriptionStatus(StrEnum):
    pass


class PaymentMethod(StrEnum):
    pass


class Command(Enum):
    START = BotCommand(command="start", description="Restart bot")
    HELP = BotCommand(command="help", description="Show help")


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


class MiddlewareEventType(StrEnum):  # https://docs.aiogram.dev/en/latest/api/types/update.html
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


class LogLevel(StrEnum):
    INFO = auto()
    DEBUG = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class ArchiveFormat(StrEnum):
    ZIP = auto()
    GZ = auto()
