from pydantic import SecretStr

from app.core.config.base import BaseConfig
from app.core.constants import API_V1, BOT_WEBHOOK_PATH


class BotConfig(BaseConfig, env_prefix="BOT_"):
    # token/secret_token are set in the dashboard (modules/settings/), not in env
    host: str = "0.0.0.0"
    port: int = 5001
    # a self-hosted telegram-bot-api server, if any
    api_url: str = "https://api.telegram.org"

    @property
    def webhook_path(self) -> str:
        return f"{API_V1}{BOT_WEBHOOK_PATH}"

    def webhook_url(self, domain: SecretStr) -> SecretStr:
        return SecretStr(f"https://{domain.get_secret_value()}{self.webhook_path}")
