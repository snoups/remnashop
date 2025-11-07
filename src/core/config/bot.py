from pydantic import SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from src.core.constants import API_V1, BOT_WEBHOOK_PATH, URL_PATTERN

from .base import BaseConfig
from .validators import validate_not_change_me, validate_username


class BotConfig(BaseConfig, env_prefix="BOT_"):
    token: SecretStr
    secret_token: SecretStr
    dev_id: int
    support_username: SecretStr
    mini_app_url: SecretStr = SecretStr("")

    reset_webhook: bool
    drop_pending_updates: bool
    setup_commands: bool
    use_banners: bool

    @property
    def webhook_path(self) -> str:
        return f"{API_V1}{BOT_WEBHOOK_PATH}"

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

    @field_validator("mini_app_url")
    @classmethod
    def validate_mini_app_url(cls, field: SecretStr, info: FieldValidationInfo) -> SecretStr:
        mini_app_url = field.get_secret_value()

        if not mini_app_url or URL_PATTERN.match(mini_app_url):
            return field

        raise ValueError(
            "BOT_MINI_APP_URL must be empty or a valid url (e.g., https://example.com/)"
        )
