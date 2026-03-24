from typing import Optional, Union

from pydantic import SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from src.core.constants import API_V1, BOT_WEBHOOK_PATH, URL_PATTERN

from .base import BaseConfig
from .validators import validate_not_change_me, validate_username


class BotConfig(BaseConfig, env_prefix="BOT_"):
    token: SecretStr
    secret_token: SecretStr
    owner_id: int
    support_username: SecretStr
    mini_app: Union[bool, SecretStr] = False

    reset_webhook: bool = False
    drop_pending_updates: bool = False
    setup_commands: bool = True
    use_banners: bool = True

    # System notifications target.
    # If system_notify_chat_id is set — system events are sent to that chat/group
    # instead of owner/admin personal chats.
    # system_notify_thread_id is optional: set it to route into a specific topic.
    system_notify_chat_id: Optional[int] = None
    system_notify_thread_id: Optional[int] = None

    @property
    def system_notify_topic_mode(self) -> bool:
        """True when system notifications should be sent to a group/topic."""
        return self.system_notify_chat_id is not None

    @property
    def webhook_path(self) -> str:
        return f"{API_V1}{BOT_WEBHOOK_PATH}"

    @property
    def is_mini_app(self) -> bool:
        if isinstance(self.mini_app, bool):
            return self.mini_app
        return bool(self.mini_app_url)

    @property
    def mini_app_url(self) -> Union[bool, str]:
        if isinstance(self.mini_app, SecretStr):
            value = self.mini_app.get_secret_value().strip()
            if value and URL_PATTERN.match(value):
                return value
        return False

    def webhook_url(self, domain: SecretStr) -> SecretStr:
        url = f"https://{domain.get_secret_value()}{self.webhook_path}"
        return SecretStr(url)

    def safe_webhook_url(self, domain: SecretStr) -> str:
        return f"https://{domain}{self.webhook_path}"

    @field_validator("token", "secret_token", "support_username")
    @classmethod
    def validate_bot_fields(cls, field: object, info: FieldValidationInfo) -> object:
        validate_not_change_me(field, info)
        return field

    @field_validator("support_username")
    @classmethod
    def validate_bot_support_username(cls, field: object, info: FieldValidationInfo) -> object:
        validate_username(field, info)
        return field

    @field_validator("mini_app")
    @classmethod
    def validate_mini_app(
        cls,
        field: Union[bool, SecretStr],
        info: FieldValidationInfo,
    ) -> Union[bool, SecretStr]:
        if isinstance(field, SecretStr):
            value = field.get_secret_value().strip().lower()
            if value.lower() == "true":
                return True
            if value.lower() == "false" or not value:
                return False
            if URL_PATTERN.match(value):
                return SecretStr(value)
            raise ValueError("BOT_MINI_APP must be empty, True, False or a valid URL")
        return field
