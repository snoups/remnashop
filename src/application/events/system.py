from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from aiogram.utils.formatting import Text

from src.__version__ import __version__
from src.application.dto import BuildInfoDto, MediaDescriptorDto, MessagePayloadDto
from src.core.constants import REPOSITORY
from src.core.enums import (
    AccessMode,
    MediaType,
    PaymentGatewayType,
    PlanType,
    PurchaseType,
    SubscriptionStatus,
    SystemNotificationType,
)
from src.core.types import NotificationType

from .base import BaseEvent, SystemEvent


@dataclass(frozen=True, kw_only=True)
class RemnashopWelcomeEvent(BaseEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.SYSTEM,
        init=False,
    )

    version: str = __version__
    repository: str = REPOSITORY

    @property
    def event_key(self) -> str:
        return "event-remnashop-welcome"

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_remnashop_keyboard  # noqa: PLC0415

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=get_remnashop_keyboard(),
            disable_default_markup=False,
            delete_after=None,
        )


@dataclass(frozen=True, kw_only=True)
class ErrorEvent(BaseEvent, BuildInfoDto):
    notification_type: NotificationType = field(
        default=SystemNotificationType.SYSTEM,
        init=False,
    )

    telegram_id: Optional[int] = field(default=None)
    username: Optional[str] = field(default=None)
    name: Optional[str] = field(default=None)

    exception: BaseException

    def as_payload(
        self,
        media: MediaDescriptorDto,
        error_type: str,
        error_message: Text,
    ) -> "MessagePayloadDto":
        data = self.__dict__.copy()
        data.pop("exception", None)

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={
                **data,
                "error": f"{error_type}: {error_message.as_html()}",
            },
            media=media,
            media_type=MediaType.DOCUMENT,
            disable_default_markup=False,
            delete_after=None,
        )

    @property
    def event_key(self) -> str:
        return "event-error.general"


@dataclass(frozen=True, kw_only=True)
class RemnawaveErrorEvent(ErrorEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.SYSTEM,
        init=False,
    )

    @property
    def event_key(self) -> str:
        return "event-error.remnawave"


@dataclass(frozen=True, kw_only=True)
class WebhookErrorEvent(BaseEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.SYSTEM,
        init=False,
    )

    @property
    def event_key(self) -> str:
        return "event-error.webhook"

    def as_payload(
        self,
        media: MediaDescriptorDto,
        error_type: str,
        error_message: Text,
    ) -> "MessagePayloadDto":
        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={
                **asdict(self),
                "error": f"{error_type}: {error_message.as_html()}",
            },
            media=media,
            media_type=MediaType.DOCUMENT,
            delete_after=None,
        )


@dataclass(frozen=True, kw_only=True)
class BotLifecycleEvent(SystemEvent, BuildInfoDto):
    notification_type: NotificationType = field(
        default=SystemNotificationType.BOT_LIFECYCLE,
        init=False,
    )


@dataclass(frozen=True, kw_only=True)
class BotStartupEvent(BotLifecycleEvent):
    access_mode: AccessMode
    payments_allowed: bool
    registration_allowed: bool

    @property
    def event_key(self) -> str:
        return "event-bot.startup"


@dataclass(frozen=True, kw_only=True)
class BotShutdownEvent(BotLifecycleEvent):
    uptime: Any

    @property
    def event_key(self) -> str:
        return "event-bot.shutdown"


@dataclass(frozen=True, kw_only=True)
class BotUpdateEvent(SystemEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.BOT_UPDATE,
        init=False,
    )

    local_version: str
    remote_version: str

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_remnashop_update_keyboard  # noqa: PLC0415

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=get_remnashop_update_keyboard(),
            disable_default_markup=False,
            delete_after=None,
        )

    @property
    def event_key(self) -> str:
        return "event-bot.update"


@dataclass(frozen=True, kw_only=True)
class UserEvent(SystemEvent):
    telegram_id: int
    username: Optional[str] = field(default=None)
    name: str


@dataclass(frozen=True, kw_only=True)
class UserRegisteredEvent(UserEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.USER_REGISTERED,
        init=False,
    )

    referrer_telegram_id: Optional[int] = field(default=None)
    referrer_username: Optional[str] = field(default=None)
    referrer_name: Optional[str] = field(default=None)

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_user_keyboard  # noqa: PLC0415

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=get_user_keyboard(self.telegram_id, self.referrer_telegram_id),
            disable_default_markup=False,
            delete_after=None,
        )

    @property
    def event_key(self) -> str:
        return "event-user.registered"


@dataclass(frozen=True, kw_only=True)
class UserFirstConnectionEvent(UserEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.USER_FIRST_CONNECTION,
        init=False,
    )

    is_trial: bool
    subscription_id: UUID
    subscription_status: SubscriptionStatus
    traffic_used: Any
    traffic_limit: Any
    device_limit: Any
    expire_time: Any

    @property
    def event_key(self) -> str:
        return "event-user.first-connected"

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_user_keyboard  # noqa: PLC0415

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=get_user_keyboard(self.telegram_id),
            disable_default_markup=False,
            delete_after=None,
        )


@dataclass(frozen=True, kw_only=True)
class UserDevicesUpdatedEvent(UserEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.USER_DEVICES_UPDATED,
        init=False,
    )

    hwid: str
    platform: Optional[str]
    device_model: Optional[str]
    os_version: Optional[str]
    user_agent: Optional[str]


@dataclass(frozen=True, kw_only=True)
class UserDeviceAddedEvent(UserDevicesUpdatedEvent):
    @property
    def event_key(self) -> str:
        return "event-user.device-added"


@dataclass(frozen=True, kw_only=True)
class UserDeviceDeletedEvent(UserDevicesUpdatedEvent):
    @property
    def event_key(self) -> str:
        return "event-user.device-deleted"


@dataclass(frozen=True, kw_only=True)
class NodeEvent(SystemEvent):
    country: str
    name: str

    address: str
    port: Optional[int]

    traffic_used: Any
    traffic_limit: Any
    last_status_message: Optional[str]
    last_status_change: Optional[str]


@dataclass(frozen=True, kw_only=True)
class NodeTrafficReachedEvent(NodeEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.NODE_TRAFFIC_REACHED,
        init=False,
    )

    @property
    def event_key(self) -> str:
        return "event-node.traffic-reached"


@dataclass(frozen=True, kw_only=True)
class NodeStatusChangedEvent(NodeEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.NODE_STATUS_CHANGED,
        init=False,
    )


@dataclass(frozen=True, kw_only=True)
class NodeConnectionLostEvent(NodeStatusChangedEvent):
    @property
    def event_key(self) -> str:
        return "event-node.connection-lost"


@dataclass(frozen=True, kw_only=True)
class NodeConnectionRestoredEvent(NodeStatusChangedEvent):
    @property
    def event_key(self) -> str:
        return "event-node.connection-restored"


@dataclass(frozen=True, kw_only=True)
class UserPurchaseEvent(UserEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.SUBSCRIPTION,
        init=False,
    )

    purchase_type: PurchaseType
    is_trial_plan: bool

    payment_id: UUID
    gateway_type: PaymentGatewayType
    final_amount: Decimal
    discount_percent: int
    original_amount: Decimal
    currency: str

    plan_name: str
    plan_type: PlanType
    plan_traffic_limit: Any
    plan_device_limit: Any
    plan_duration: Any

    previous_plan_name: Any = None
    previous_plan_type: Any = None
    previous_plan_traffic_limit: Any = None
    previous_plan_device_limit: Any = None
    previous_plan_duration: Any = None

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_user_keyboard  # noqa: PLC0415

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=get_user_keyboard(self.telegram_id),
            disable_default_markup=False,
            delete_after=None,
        )

    @property
    def event_key(self) -> str:
        match self.purchase_type:
            case PurchaseType.NEW:
                return "event-subscription.new"
            case PurchaseType.RENEW:
                return "event-subscription.renew"
            case PurchaseType.CHANGE:
                return "event-subscription.change"


@dataclass(frozen=True, kw_only=True)
class TrialActivatedEvent(UserEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.TRIAL_ACTIVATED,
        init=False,
    )

    is_trial_plan: bool = True
    plan_name: str
    plan_type: PlanType
    plan_traffic_limit: Any
    plan_device_limit: Any
    plan_duration: Any

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_user_keyboard  # noqa: PLC0415

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=get_user_keyboard(self.telegram_id),
            disable_default_markup=False,
            delete_after=None,
        )

    @property
    def event_key(self) -> str:
        return "event-subscription.trial"


@dataclass(frozen=True, kw_only=True)
class SubscriptionRevokedEvent(UserEvent):
    notification_type: NotificationType = field(
        default=SystemNotificationType.USER_REVOKED_SUBSCRIPTION,
        init=False,
    )

    is_trial: bool
    subscription_id: UUID
    subscription_status: SubscriptionStatus
    traffic_used: Any
    traffic_limit: Any
    device_limit: Any
    expire_time: Any

    @property
    def event_key(self) -> str:
        return "event-subscription.revoked"
