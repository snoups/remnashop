from enum import Enum, IntEnum, StrEnum, auto
from typing import Self, Union

from aiogram.types import BotCommand, ContentType


class UpperStrEnum(StrEnum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name


class ButtonType(UpperStrEnum):
    URL = auto()
    COPY = auto()
    WEB_APP = auto()


class BroadcastStatus(UpperStrEnum):
    PROCESSING = auto()
    COMPLETED = auto()
    CANCELED = auto()
    DELETED = auto()
    ERROR = auto()


class BroadcastMessageStatus(UpperStrEnum):
    SENT = auto()
    FAILED = auto()
    EDITED = auto()
    DELETED = auto()
    PENDING = auto()


class BroadcastAudience(UpperStrEnum):
    ALL = auto()
    PLAN = auto()
    SUBSCRIBED = auto()
    UNSUBSCRIBED = auto()
    EXPIRED = auto()
    TRIAL = auto()


class PlanType(UpperStrEnum):
    TRAFFIC = auto()
    DEVICES = auto()
    BOTH = auto()
    UNLIMITED = auto()


class PlanAvailability(UpperStrEnum):
    ALL = auto()
    NEW = auto()
    EXISTING = auto()
    INVITED = auto()
    ALLOWED = auto()
    LINK = auto()


class PaymentGatewayType(UpperStrEnum):
    TELEGRAM_STARS = auto()
    YOOKASSA = auto()
    YOOMONEY = auto()
    CRYPTOMUS = auto()
    HELEKET = auto()
    CRYPTOPAY = auto()
    FREEKASSA = auto()
    MULENPAY = auto()
    PAYMASTER = auto()
    PLATEGA = auto()
    ROBOKASSA = auto()
    URLPAY = auto()
    WATA = auto()


class PurchaseType(UpperStrEnum):
    NEW = auto()
    RENEW = auto()
    CHANGE = auto()


class TransactionStatus(UpperStrEnum):
    PENDING = auto()
    COMPLETED = auto()
    CANCELED = auto()
    REFUNDED = auto()
    FAILED = auto()


class SubscriptionStatus(UpperStrEnum):
    ACTIVE = auto()
    DISABLED = auto()
    LIMITED = auto()
    EXPIRED = auto()
    DELETED = auto()


class ReferralRewardType(UpperStrEnum):
    POINTS = auto()
    EXTRA_DAYS = auto()


class ReferralLevel(IntEnum):
    FIRST = auto()
    SECOND = auto()


class ReferralAccrualStrategy(UpperStrEnum):
    ON_FIRST_PAYMENT = auto()
    ON_EACH_PAYMENT = auto()


class ReferralRewardStrategy(UpperStrEnum):
    AMOUNT = auto()
    PERCENT = auto()


class BannerName(StrEnum):
    DEFAULT = auto()
    MENU = auto()
    DASHBOARD = auto()
    SUBSCRIPTION = auto()
    PROMOCODE = auto()
    REFERRAL = auto()


class BannerFormat(StrEnum):
    JPG = auto()
    JPEG = auto()
    PNG = auto()
    GIF = auto()
    WEBP = auto()

    @property
    def content_type(self) -> ContentType:
        if self == self.GIF:
            return ContentType.ANIMATION
        else:
            return ContentType.PHOTO


class MessageEffectId(StrEnum):
    # 👍 Thumbs Up
    THUMBS_UP = "5107584321108051014"

    # 👎 Thumbs Down
    THUMBS_DOWN = "5104858069142078462"

    # ❤️ Heart
    HEART = "5159385139981059251"

    # 🔥 Fire
    FIRE = "5104841245755180586"

    # 🎉 Party Popper
    PARTY = "5046509860389126442"

    # 💩 Pile of Poo
    POOP = "5046589136895476101"


class MediaType(UpperStrEnum):
    PHOTO = auto()
    VIDEO = auto()
    DOCUMENT = auto()


class Role(IntEnum):
    USER = auto()
    PREVIEW = auto()
    ADMIN = auto()
    DEV = auto()
    OWNER = auto()
    SYSTEM = auto()

    def __str__(self) -> str:
        return self.name

    def includes(self, other: "Role") -> bool:
        return self >= other

    def get_subordinates(self) -> list["Role"]:
        return [r for r in Role if self > r and r > Role.USER]


class SystemNotificationType(UpperStrEnum):
    SYSTEM = auto()
    #
    BOT_LIFECYCLE = auto()
    BOT_UPDATE = auto()
    #
    USER_REGISTERED = auto()
    SUBSCRIPTION = auto()
    PROMOCODE_ACTIVATED = auto()
    TRIAL_ACTIVATED = auto()
    #
    NODE_STATUS_CHANGED = auto()
    NODE_TRAFFIC_REACHED = auto()
    #
    USER_FIRST_CONNECTION = auto()
    USER_DEVICES_UPDATED = auto()
    USER_REVOKED_SUBSCRIPTION = auto()


class UserNotificationType(UpperStrEnum):
    EXPIRES_IN_3_DAYS = auto()
    EXPIRES_IN_2_DAYS = auto()
    EXPIRES_IN_1_DAY = auto()
    #
    EXPIRED = auto()
    EXPIRED_1_DAY_AGO = auto()
    LIMITED = auto()
    #
    REFERRAL_ATTACHED = auto()
    REFERRAL_REWARD_RECEIVED = auto()


class AccessMode(UpperStrEnum):
    PUBLIC = auto()  # Access is allowed for everyone
    INVITED = auto()  # Invited users only
    RESTRICTED = auto()  # All actions are completely forbidden


class AccessRequirements(StrEnum):
    RULES = auto()
    CHANNEL = auto()


class Currency(UpperStrEnum):
    USD = auto()
    XTR = auto()
    RUB = auto()

    @property
    def symbol(self) -> str:
        symbols = {
            self.USD: "$",
            self.XTR: "★",
            self.RUB: "₽",
        }
        return symbols.get(self, "?")

    @classmethod
    def from_code(cls, code: str) -> Self:
        return cls(code.upper())

    @classmethod
    def from_gateway_type(cls, gateway_type: PaymentGatewayType) -> "Currency":
        mapping = {
            PaymentGatewayType.TELEGRAM_STARS: cls.XTR,
            PaymentGatewayType.YOOKASSA: cls.RUB,
            PaymentGatewayType.YOOMONEY: cls.RUB,
            PaymentGatewayType.CRYPTOMUS: cls.USD,
            PaymentGatewayType.HELEKET: cls.USD,
            PaymentGatewayType.CRYPTOPAY: cls.USD,
            PaymentGatewayType.FREEKASSA: cls.RUB,
            PaymentGatewayType.MULENPAY: cls.RUB,
            PaymentGatewayType.PAYMASTER: cls.RUB,
            PaymentGatewayType.PLATEGA: cls.RUB,
            PaymentGatewayType.ROBOKASSA: cls.RUB,
            PaymentGatewayType.URLPAY: cls.RUB,
            PaymentGatewayType.WATA: cls.RUB,
        }

        try:
            return mapping[gateway_type]
        except KeyError:
            raise ValueError(f"Unknown payment gateway type: '{gateway_type}'")

    def amount(self, amount: Union[float, int]) -> str:
        return f"{amount} {self.symbol}"


class Command(Enum):
    START = BotCommand(command="start", description="command.start")
    PAYSUPPORT = BotCommand(command="paysupport", description="command.paysupport")
    RULES = BotCommand(command="rules", description="command.rules")
    HELP = BotCommand(command="help", description="command.help")


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


class LogLevel(UpperStrEnum):
    CRITICAL = auto()
    FATAL = auto()
    ERROR = auto()
    WARN = auto()
    WARNING = auto()
    INFO = auto()
    DEBUG = auto()
    NOTSET = auto()
