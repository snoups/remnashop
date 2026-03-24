from dataclasses import asdict, dataclass, field
from typing import Any

from remnapy.enums.users import TrafficLimitStrategy

from src.application.dto.message_payload import MessagePayloadDto
from src.core.enums import MessageEffectId, ReferralRewardType, UserNotificationType
from src.core.types import NotificationType

from .base import UserEvent


@dataclass(frozen=True, kw_only=True)
class SubscriptionLimitedEvent(UserEvent):
    notification_type: NotificationType = field(
        default=UserNotificationType.LIMITED,
        init=False,
    )

    is_trial: bool
    traffic_strategy: TrafficLimitStrategy
    reset_time: Any

    @property
    def event_key(self) -> str:
        return "event-subscription.limited"

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_buy_keyboard, get_renew_keyboard  # noqa: PLC0415

        keyboard = get_buy_keyboard() if self.is_trial else get_renew_keyboard()

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=keyboard,
            disable_default_markup=False,
            delete_after=None,
        )


@dataclass(frozen=True, kw_only=True)
class SubscriptionExpiredEvent(UserEvent):
    notification_type: NotificationType = field(
        default=UserNotificationType.EXPIRED,
        init=True,
    )

    is_trial: bool

    @property
    def event_key(self) -> str:
        return "event-subscription.expired"

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_buy_keyboard, get_renew_keyboard  # noqa: PLC0415

        keyboard = get_buy_keyboard() if self.is_trial else get_renew_keyboard()

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=keyboard,
            disable_default_markup=False,
            delete_after=None,
        )


@dataclass(frozen=True, kw_only=True)
class SubscriptionExpiresEvent(UserEvent):
    notification_type: NotificationType = field(
        default=UserNotificationType.EXPIRES_IN_1_DAY,
        init=True,
    )

    is_trial: bool
    day: int

    @property
    def event_key(self) -> str:
        return "event-subscription.expiring"

    def as_payload(self) -> "MessagePayloadDto":
        from src.telegram.keyboards import get_buy_keyboard, get_renew_keyboard  # noqa: PLC0415

        keyboard = get_buy_keyboard() if self.is_trial else get_renew_keyboard()

        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            reply_markup=keyboard,
            disable_default_markup=False,
            delete_after=None,
        )


@dataclass(frozen=True, kw_only=True)
class ReferralEvent(UserEvent):
    name: str


@dataclass(frozen=True, kw_only=True)
class ReferralAttachedEvent(ReferralEvent):
    notification_type: NotificationType = field(
        default=UserNotificationType.REFERRAL_ATTACHED,
        init=True,
    )

    @property
    def event_key(self) -> str:
        return "event-referral.attached"


@dataclass(frozen=True, kw_only=True)
class ReferralRewardEvent(ReferralEvent):
    value: int
    reward_type: ReferralRewardType


@dataclass(frozen=True, kw_only=True)
class ReferralRewardReceivedEvent(ReferralRewardEvent):
    notification_type: NotificationType = field(
        default=UserNotificationType.REFERRAL_REWARD_RECEIVED,
        init=True,
    )

    @property
    def event_key(self) -> str:
        return "event-referral.reward"

    def as_payload(self) -> "MessagePayloadDto":
        return MessagePayloadDto(
            i18n_key=self.event_key,
            i18n_kwargs={**asdict(self)},
            disable_default_markup=False,
            delete_after=None,
            message_effect=MessageEffectId.PARTY,
        )


@dataclass(frozen=True, kw_only=True)
class ReferralRewardFailedEvent(ReferralRewardEvent):
    notification_type: NotificationType = field(
        default=UserNotificationType.REFERRAL_REWARD_RECEIVED,
        init=True,
    )

    @property
    def event_key(self) -> str:
        return "event-referral.reward-failed"
