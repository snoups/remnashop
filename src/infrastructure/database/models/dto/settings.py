from typing import Optional

from pydantic import Field, SecretStr

from src.core.constants import T_ME
from src.core.enums import (
    AccessMode,
    Currency,
    ReferralAccrualStrategy,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
    SystemNotificationType,
    UserNotificationType,
)

from .base import BaseDto, TrackableDto


class SystemNotificationDto(TrackableDto):  # == SystemNotificationType
    bot_lifetime: bool = True
    bot_update: bool = True
    user_registered: bool = True
    subscription: bool = True
    promocode_activated: bool = True
    trial_getted: bool = True
    node_status: bool = True
    user_first_connected: bool = True
    user_hwid: bool = True
    # TODO: Add torrent_block
    # TODO: Add traffic_overuse

    def is_enabled(self, ntf_type: SystemNotificationType) -> bool:
        return getattr(self, ntf_type.value.lower(), False)


class UserNotificationDto(TrackableDto):  # == UserNotificationType
    expires_in_3_days: bool = True
    expires_in_2_days: bool = True
    expires_in_1_days: bool = True
    expired: bool = True
    limited: bool = True
    expired_1_day_ago: bool = True
    referral_attached: bool = True
    referral_reward: bool = True

    def is_enabled(self, ntf_type: UserNotificationType) -> bool:
        return getattr(self, ntf_type.value.lower(), False)


class ReferralRewardSettingsDto(BaseDto):
    type: ReferralRewardType = ReferralRewardType.EXTRA_DAYS
    strategy: ReferralRewardStrategy = ReferralRewardStrategy.AMOUNT
    config: dict[ReferralLevel, int] = {ReferralLevel.FIRST: 5}

    @property
    def is_identical(self) -> bool:
        values = list(self.config.values())
        return len(values) <= 1 or all(v == values[0] for v in values)

    @property
    def is_points(self) -> bool:
        return self.type == ReferralRewardType.POINTS

    @property
    def is_extra_days(self) -> bool:
        return self.type == ReferralRewardType.EXTRA_DAYS


class ReferralSettingsDto(TrackableDto):
    enable: bool = True
    level: ReferralLevel = ReferralLevel.FIRST
    accrual_strategy: ReferralAccrualStrategy = ReferralAccrualStrategy.ON_FIRST_PAYMENT
    reward: ReferralRewardSettingsDto = ReferralRewardSettingsDto()


class SettingsDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    rules_required: bool = False
    channel_required: bool = False

    rules_link: SecretStr = SecretStr("https://telegram.org/tos/")
    channel_id: Optional[int] = False
    channel_link: SecretStr = SecretStr("@remna_shop")

    access_mode: AccessMode = AccessMode.PUBLIC
    purchases_allowed: bool = True
    registration_allowed: bool = True

    default_currency: Currency = Currency.XTR

    user_notifications: UserNotificationDto = UserNotificationDto()
    system_notifications: SystemNotificationDto = SystemNotificationDto()

    referral: ReferralSettingsDto = ReferralSettingsDto()

    @property
    def channel_has_username(self) -> bool:
        return self.channel_link.get_secret_value().startswith("@")

    @property
    def get_url_channel_link(self) -> str:
        if self.channel_has_username:
            return f"{T_ME}{self.channel_link.get_secret_value()[1:]}"
        else:
            return self.channel_link.get_secret_value()
