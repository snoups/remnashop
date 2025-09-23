from enum import Enum, IntEnum, StrEnum, auto
from typing import Any, Callable, Union

from aiogram import Bot
from aiogram.types import BotCommand, ContentType


class UpperStrEnum(StrEnum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name


class TransactionStatus(UpperStrEnum):
    PENDING = auto()
    COMPLETED = auto()
    CANCELED = auto()
    REFUNDED = auto()


class SubscriptionStatus(UpperStrEnum):
    ACTIVE = auto()
    DISABLED = auto()
    LIMITED = auto()
    EXPIRED = auto()


class TrafficLimitStrategy(UpperStrEnum):
    NO_RESET = auto()
    DAY = auto()
    WEEK = auto()
    MONTH = auto()


class MessageEffect(UpperStrEnum):
    FIRE = "5104841245755180586"  #     🔥
    LIKE = "5107584321108051014"  #     👍
    DISLIKE = "5104858069142078462"  #  👎
    LOVE = "5159385139981059251"  #     ❤️
    CONFETTI = "5046509860389126442"  # 🎉
    POOP = "5046589136895476101"  #     💩


class BannerName(UpperStrEnum):
    DEFAULT = auto()
    MENU = auto()
    DASHBOARD = auto()
    SUBSCRIPTION = auto()


class BannerFormat(UpperStrEnum):
    JPG = auto()
    JPEG = auto()
    PNG = auto()
    GIF = auto()
    WEBP = auto()

    @property
    def content_type(self) -> ContentType:
        match self:
            case BannerFormat.JPG | BannerFormat.JPEG | BannerFormat.PNG | BannerFormat.WEBP:
                return ContentType.PHOTO
            case BannerFormat.GIF:
                return ContentType.ANIMATION


class MediaType(UpperStrEnum):
    PHOTO = auto()
    VIDEO = auto()
    DOCUMENT = auto()

    def get_function(self, bot_instance: Bot) -> Callable[..., Any]:
        match self:
            case MediaType.PHOTO:
                return bot_instance.send_photo
            case MediaType.VIDEO:
                return bot_instance.send_video
            case MediaType.DOCUMENT:
                return bot_instance.send_document


class SystemNotificationType(UpperStrEnum):
    BOT_LIFETIME = auto()
    USER_REGISTERED = auto()
    SUBSCRIPTION = auto()
    PROMOCODE_ACTIVATED = auto()


class UserNotificationType(UpperStrEnum):
    pass


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


class PromocodeRewardType(UpperStrEnum):
    DURATION = auto()
    TRAFFIC = auto()
    SUBSCRIPTION = auto()
    PERSONAL_DISCOUNT = auto()
    PURCHASE_DISCOUNT = auto()


class PlanType(UpperStrEnum):
    TRAFFIC = auto()
    DEVICES = auto()
    BOTH = auto()
    UNLIMITED = auto()
    # TODO: TRIAL = auto() ???


class PlanAvailability(UpperStrEnum):
    ALL = auto()
    NEW = auto()
    EXISTING = auto()
    INVITED = auto()
    ALLOWED = auto()


class Currency(UpperStrEnum):
    USD = auto()
    XTR = auto()
    RUB = auto()

    @property
    def symbol(self) -> str:
        symbols = {
            "USD": "$",
            "XTR": "★",
            "RUB": "₽",
        }
        return symbols[self.value]

    @classmethod
    def from_code(cls, code: str) -> "Currency":
        return cls(code)


class PaymentGatewayType(UpperStrEnum):
    TELEGRAM_STARS = auto()
    YOOKASSA = auto()
    YOOMONEY = auto()
    CRYPTOMUS = auto()
    HELEKET = auto()
    # TRIBUTE = auto()


class MaintenanceMode(UpperStrEnum):
    GLOBAL = auto()
    PURCHASE = auto()
    OFF = auto()

    # BotAccessMode.ALL: "Разрешен для всех",
    # BotAccessMode.INVITED: "Разрешен для приглашенных",
    # BotAccessMode.NO_PURCHASES: "Запрещены покупки",
    # BotAccessMode.BLOCKED: "Запрещены любые действия",


class Command(Enum):
    START = BotCommand(command="start", description="cmd-start")
    # HELP = BotCommand(command="help", description="cmd-help")


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


# https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#vat-codes
class YookassaVatCode(IntEnum):
    VAT_CODE_01 = auto()  # Without VAT
    VAT_CODE_02 = auto()  # VAT at 0% rate
    VAT_CODE_03 = auto()  # VAT at 10% rate
    VAT_CODE_04 = auto()  # VAT at 20% rate
    VAT_CODE_05 = auto()  # VAT at calculated rate 10/110
    VAT_CODE_06 = auto()  # VAT at calculated rate 20/120
    VAT_CODE_07 = auto()  # VAT at 5% rate
    VAT_CODE_08 = auto()  # VAT at 7% rate
    VAT_CODE_09 = auto()  # VAT at calculated rate 5/105
    VAT_CODE_10 = auto()  # VAT at calculated rate 7/107
