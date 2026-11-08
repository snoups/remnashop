from enum import IntEnum, StrEnum, auto
from typing import Optional


class UpperStrEnum(StrEnum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name


class PaymentGatewayType(UpperStrEnum):
    TELEGRAM_STARS = auto()
    YOOKASSA = auto()
    YOOMONEY = auto()
    VALUTIX = auto()
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
    ROLLYPAY = auto()
    ANTILOPAY = auto()
    PAYPALYCH = auto()
    RIOPAY = auto()
    AURAPAY = auto()
    SEVERPAY = auto()
    LAVA = auto()
    CLOUDPAYMENTS = auto()
    PAYPEAR = auto()


class PaymentOutcome(UpperStrEnum):
    SUCCEEDED = auto()
    NOT_FULFILLED = auto()
    CANCELED = auto()


class PlanType(UpperStrEnum):
    TRAFFIC = auto()
    DEVICES = auto()
    BOTH = auto()
    UNLIMITED = auto()


# a fixed set so the clients translate it, no per-plan texts
class PlanBadge(UpperStrEnum):
    POPULAR = auto()
    BEST_VALUE = auto()


class PlanAvailability(UpperStrEnum):
    ALL = auto()
    NEW = auto()
    EXISTING = auto()
    INVITED = auto()
    ALLOWED = auto()
    LINK = auto()


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


class RoundingMode(UpperStrEnum):
    INTEGER = auto()
    DECIMAL_2 = auto()


class PriceAdjustScope(UpperStrEnum):
    ALL_PLANS = auto()
    ALL_ADDONS = auto()
    SELECTED = auto()


class PriceAdjustMode(UpperStrEnum):
    MULTIPLY = auto()
    SET = auto()
    # plan durations only: the base duration's price per day times the days, less a
    # per-duration discount
    LADDER = auto()


class PinnedPriceAction(UpperStrEnum):
    KEEP = auto()
    # by the same ratio as the base price
    SCALE = auto()
    RESET = auto()


class DiscountSource(UpperStrEnum):
    NONE = auto()
    PERSONAL = auto()
    PURCHASE = auto()
    LOYALTY = auto()


class SubscriptionStatus(UpperStrEnum):
    ACTIVE = auto()
    LIMITED = auto()
    EXPIRED = auto()
    DISABLED = auto()
    DELETED = auto()


class AddOnType(UpperStrEnum):
    TRAFFIC = auto()
    DEVICES = auto()


class PanelSyncDirection(UpperStrEnum):
    FROM_PANEL = auto()
    TO_PANEL = auto()


class PromocodeRewardType(UpperStrEnum):
    DURATION = auto()
    TRAFFIC = auto()
    DEVICES = auto()
    SUBSCRIPTION = auto()
    PERSONAL_DISCOUNT = auto()
    PURCHASE_DISCOUNT = auto()


# derived from is_active + expires_at; never stored
class PromocodeStatus(UpperStrEnum):
    ACTIVE = auto()
    EXPIRED = auto()
    INACTIVE = auto()
    # live, but its activation limit is used up
    EXHAUSTED = auto()


class PromocodeAvailability(UpperStrEnum):
    ALL = auto()
    NEW = auto()
    EXISTING = auto()
    INVITED = auto()
    ALLOWED = auto()


class PurchaseType(UpperStrEnum):
    NEW = auto()
    RENEW = auto()
    CHANGE = auto()


class PurchaseChannel(UpperStrEnum):
    BOT = auto()
    CABINET = auto()


class LegalDocumentKind(UpperStrEnum):
    OFFER = auto()
    USER_AGREEMENT = auto()
    PRIVACY_POLICY = auto()


class LegalAcceptanceTrigger(UpperStrEnum):
    SIGN_UP = auto()
    PAYMENT = auto()


class ReferralLevel(IntEnum):
    FIRST = auto()
    SECOND = auto()
    THIRD = auto()


class ReferralRewardType(UpperStrEnum):
    EXTRA_DAYS = auto()
    POINTS = auto()


class ReferralAccrualStrategy(UpperStrEnum):
    FIRST_PAYMENT = auto()
    EVERY_PAYMENT = auto()


class ReferralRewardStrategy(UpperStrEnum):
    AMOUNT = auto()
    PERCENT = auto()


class RegistrationSource(UpperStrEnum):
    BOT = auto()
    CABINET_TELEGRAM = auto()
    CABINET_MINI_APP = auto()
    CABINET_BOT_LINK = auto()
    CABINET_EMAIL = auto()
    CABINET_GOOGLE = auto()
    CABINET_YANDEX = auto()


class AdLinkChannel(UpperStrEnum):
    BOT = auto()
    WEBCABINET = auto()


class AccessMode(UpperStrEnum):
    PUBLIC = auto()
    INVITED = auto()
    RESTRICTED = auto()


class CaptchaProvider(UpperStrEnum):
    TURNSTILE = auto()
    HCAPTCHA = auto()


class SmtpSecurity(UpperStrEnum):
    STARTTLS = auto()
    TLS = auto()
    NONE = auto()


class EmailOutcome(UpperStrEnum):
    SENT = auto()
    REFUSED = auto()
    RETRY = auto()


class AccessDenial(UpperStrEnum):
    RESTRICTED = auto()
    REGISTRATION_DISABLED = auto()
    INVITE_ONLY = auto()


class SessionAudience(UpperStrEnum):
    DASHBOARD = auto()
    CABINET = auto()


class CabinetSignInMethod(UpperStrEnum):
    TELEGRAM = auto()
    EMAIL = auto()
    GOOGLE = auto()
    YANDEX = auto()


class TransactionStatus(UpperStrEnum):
    PENDING = auto()
    PAID = auto()
    FAILED = auto()
    CANCELED = auto()
    REFUNDED = auto()


class BroadcastStatus(UpperStrEnum):
    DRAFT = auto()
    SCHEDULED = auto()
    SENDING = auto()
    COMPLETED = auto()
    CANCELED = auto()
    FAILED = auto()


class BroadcastCategory(UpperStrEnum):
    SERVICE = auto()
    MARKETING = auto()


class BroadcastDelivery(UpperStrEnum):
    TELEGRAM = auto()
    EMAIL = auto()
    ALL = auto()


class BroadcastChannel(UpperStrEnum):
    TELEGRAM = auto()
    EMAIL = auto()


class BroadcastRecipientStatus(UpperStrEnum):
    PENDING = auto()
    SENT = auto()
    FAILED = auto()
    BLOCKED = auto()
    CANCELED = auto()
    RECALLED = auto()


class BroadcastButtonKind(UpperStrEnum):
    URL = auto()
    PROMOCODE = auto()
    MENU = auto()


class BroadcastMediaType(UpperStrEnum):
    PHOTO = auto()
    VIDEO = auto()
    ANIMATION = auto()
    DOCUMENT = auto()


class BroadcastSubscriptionFilter(UpperStrEnum):
    ACTIVE = auto()
    TRIAL = auto()
    EXPIRED = auto()
    LIMITED = auto()
    NONE = auto()


class BackupKind(UpperStrEnum):
    DATABASE = auto()
    ASSETS = auto()


class BackupRunStatus(UpperStrEnum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELED = auto()


class BlacklistKind(UpperStrEnum):
    TELEGRAM_ID = auto()
    EMAIL = auto()


class OAuthProvider(UpperStrEnum):
    GITHUB = auto()
    TELEGRAM = auto()
    OIDC = auto()
    GOOGLE = auto()
    YANDEX = auto()

    @classmethod
    def _missing_(cls, value: object) -> Optional["OAuthProvider"]:
        # path params arrive lowercase ("github"), values are uppercase; only
        # this enum is lenient, the rest of UpperStrEnum stays strict
        return cls.__members__.get(value.upper()) if isinstance(value, str) else None


class Role(IntEnum):
    USER = auto()
    ADMIN = auto()
    OWNER = auto()
    SYSTEM = auto()

    def __str__(self) -> str:
        return self.name

    def includes(self, other: "Role") -> bool:
        return self >= other


# https://docs.aiogram.dev/en/latest/api/types/update.html
class MiddlewareEventType(StrEnum):
    AIOGD_UPDATE = auto()  # aiogram-dialog
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
    BG = auto()  # Bulgarian
    CS = auto()  # Czech
    DA = auto()  # Danish
    DE = auto()  # German
    EL = auto()  # Greek
    EN = auto()  # English
    ES = auto()  # Spanish
    FA = auto()  # Persian
    FI = auto()  # Finnish
    FR = auto()  # French
    HE = auto()  # Hebrew
    HI = auto()  # Hindi
    HU = auto()  # Hungarian
    ID = auto()  # Indonesian
    IT = auto()  # Italian
    JA = auto()  # Japanese
    KK = auto()  # Kazakh
    KO = auto()  # Korean
    MS = auto()  # Malay
    NL = auto()  # Dutch
    NO = auto()  # Norwegian
    PL = auto()  # Polish
    PT = auto()  # Portuguese
    RO = auto()  # Romanian
    RU = auto()  # Russian
    SR = auto()  # Serbian
    SV = auto()  # Swedish
    TG = auto()  # Tajik
    TH = auto()  # Thai
    TR = auto()  # Turkish
    UK = auto()  # Ukrainian
    UZ = auto()  # Uzbek
    VI = auto()  # Vietnamese
    ZH = auto()  # Chinese


class LogLevel(UpperStrEnum):
    CRITICAL = auto()
    FATAL = auto()
    ERROR = auto()
    WARN = auto()
    WARNING = auto()
    INFO = auto()
    DEBUG = auto()
    NOTSET = auto()


class BannerFormat(StrEnum):
    JPG = auto()
    JPEG = auto()
    PNG = auto()
    GIF = auto()
    WEBP = auto()


class AppearanceImageKind(StrEnum):
    LOGO = auto()
    FAVICON = auto()


class AppearanceTarget(StrEnum):
    DASHBOARD = auto()
    CABINET = auto()


class AppearanceImageFormat(StrEnum):
    JPG = auto()
    PNG = auto()
    WEBP = auto()
    SVG = auto()


class DialogWindowKind(StrEnum):
    SEED = auto()
    CUSTOM = auto()


class DialogFlow(StrEnum):
    MENU = auto()
    PURCHASE = auto()
    RENEWAL = auto()
    CHANGE = auto()
    SUBSCRIPTION = auto()
    PROMOCODE = auto()
    REFERRALS = auto()
    CUSTOM = auto()


class ButtonLinkType(StrEnum):
    ACTION = auto()
    NAVIGATE = auto()
    URL = auto()
    WEB_APP = auto()


class ButtonStyleKind(StrEnum):
    PRIMARY = auto()
    SUCCESS = auto()
    DANGER = auto()
