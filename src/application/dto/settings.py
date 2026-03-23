from dataclasses import dataclass, field
from typing import Optional

from pydantic import SecretStr

from src.core.constants import REPOSITORY, T_ME
from src.core.enums import (
    AccessMode,
    ButtonType,
    Currency,
    ReferralAccrualStrategy,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
    Role,
    SystemNotificationType,
    UserNotificationType,
)
from src.core.types import NotificationType

from .base import BaseDto, TimestampMixin, TrackableMixin


def get_default_notifications() -> dict[str, bool]:
    system_keys = {ntf.value: True for ntf in SystemNotificationType}
    user_keys = {ntf.value: True for ntf in UserNotificationType}
    return {**system_keys, **user_keys}


@dataclass(kw_only=True)
class AccessSettingsDto(TrackableMixin):
    mode: AccessMode = AccessMode.PUBLIC
    registration_allowed: bool = True
    payments_allowed: bool = True

    def can_register(self) -> bool:
        if self.mode == AccessMode.RESTRICTED:
            return False
        return self.registration_allowed


@dataclass(kw_only=True)
class RequirementSettingsDto(TrackableMixin):
    rules_required: bool = False
    channel_required: bool = False

    rules_link: SecretStr = SecretStr("https://telegram.org/tos/")
    channel_id: Optional[int] = None
    channel_link: SecretStr = SecretStr("@remna_shop")

    @property
    def rules_url(self) -> str:
        return self.rules_link.get_secret_value()

    @property
    def channel_has_username(self) -> bool:
        return self.channel_link.get_secret_value().startswith("@")

    @property
    def channel_url(self) -> str:
        url = self.channel_link.get_secret_value()
        if self.channel_has_username:
            return f"{T_ME}{url[1:]}"
        return url


@dataclass(kw_only=True)
class NotificationsSettingsDto(TrackableMixin):
    settings: dict[str, bool] = field(default_factory=get_default_notifications)

    def is_enabled(self, ntf_type: NotificationType) -> bool:
        return self.settings.get(ntf_type, True)

    def toggle(self, ntf_type: NotificationType) -> None:
        new_settings = self.settings.copy()
        new_settings[ntf_type] = not self.is_enabled(ntf_type)
        self.settings = new_settings

    @property
    def system(self) -> list[tuple[str, bool]]:
        return [
            (ntf.value, self.is_enabled(SystemNotificationType(ntf.value)))
            for ntf in SystemNotificationType
        ]

    @property
    def user(self) -> list[tuple[str, bool]]:
        return [
            (ntf.value, self.is_enabled(UserNotificationType(ntf.value)))
            for ntf in UserNotificationType
        ]


@dataclass(kw_only=True)
class ReferralRewardSettingsDto(TrackableMixin):
    type: ReferralRewardType = ReferralRewardType.EXTRA_DAYS
    strategy: ReferralRewardStrategy = ReferralRewardStrategy.AMOUNT
    config: dict[ReferralLevel, int] = field(default_factory=lambda: {ReferralLevel.FIRST: 5})

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


@dataclass(kw_only=True)
class ReferralSettingsDto(TrackableMixin):
    enable: bool = True
    level: ReferralLevel = ReferralLevel.FIRST
    accrual_strategy: ReferralAccrualStrategy = ReferralAccrualStrategy.ON_FIRST_PAYMENT
    reward: ReferralRewardSettingsDto = field(default_factory=ReferralRewardSettingsDto)


@dataclass(kw_only=True)
class MenuButtonDto(TrackableMixin):
    index: int
    text: str = "btn-test"
    type: ButtonType = ButtonType.URL
    payload: str = REPOSITORY
    is_active: bool = False
    required_role: Role = Role.USER


@dataclass(kw_only=True)
class MenuSettingsDto(TrackableMixin):
    buttons: list[MenuButtonDto] = field(
        default_factory=lambda: [MenuButtonDto(index=i) for i in range(1, 7)]
    )


@dataclass(kw_only=True)
class BackupSettingsDto(TrackableMixin):
    enabled: bool = False
    interval_hours: int = 24
    max_files: int = 7
    send_to_chat: bool = True


@dataclass(kw_only=True)
class SettingsDto(BaseDto, TrackableMixin, TimestampMixin):
    default_currency: Currency = Currency.XTR
    access: AccessSettingsDto = field(default_factory=AccessSettingsDto)
    requirements: RequirementSettingsDto = field(default_factory=RequirementSettingsDto)
    notifications: NotificationsSettingsDto = field(default_factory=NotificationsSettingsDto)
    referral: ReferralSettingsDto = field(default_factory=ReferralSettingsDto)
    menu: MenuSettingsDto = field(default_factory=MenuSettingsDto)
    backup: BackupSettingsDto = field(default_factory=BackupSettingsDto)
