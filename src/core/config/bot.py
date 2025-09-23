from pydantic import SecretStr, field_validator
from pydantic_core.core_schema import FieldValidationInfo

from src.core.constants import API_V1, BOT_WEBHOOK_PATH

from .base import BaseConfig
from .validators import validate_not_change_me


class BotConfig(BaseConfig, env_prefix="BOT_"):
    token: SecretStr
    secret_token: SecretStr
    dev_id: int

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

    @field_validator("token", "secret_token")
    @classmethod
    def validate_bot_fields(cls, field: object, info: FieldValidationInfo) -> object:
        validate_not_change_me(field, info)
        return field
