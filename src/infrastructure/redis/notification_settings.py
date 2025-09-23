from typing import Any

from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict, Field

from src.core.utils.types import AnyNotification


class RedisDto(_BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        from_attributes=True,
        populate_by_name=True,
    )


class NotificationSettingsMixin(RedisDto):
    @property
    def list_data(self) -> list[dict[str, Any]]:
        return [
            {
                "type": field.upper(),
                "enabled": value,
            }
            for field, value in self.model_dump().items()
        ]

    def toggle_notification(self, notification_type: AnyNotification) -> bool:
        field_name = notification_type.value.lower()
        current_data = self.model_dump()

        if field_name not in current_data:
            raise ValueError(f"Invalid notification type: {notification_type}")

        current_data[field_name] = not current_data[field_name]
        self.__dict__.update(current_data)
        return bool(current_data[field_name])


class SystemNotificationDto(NotificationSettingsMixin):
    bot_lifetime: bool = Field(default=True)
    user_registered: bool = Field(default=True)
    subscription: bool = Field(default=True)
    promocode_activated: bool = Field(default=True)
    # TODO: torrent_block
    # TODO: traffic_overuse


class UserNotificationDto(NotificationSettingsMixin):
    # subscription_3_days_left: bool = Field(default=True)
    # subscription_24_hours_left: bool = Field(default=True)
    # subscription_ended: bool = Field(default=True)
    # available_after_maintenance: bool = Field(default=True)
    pass
