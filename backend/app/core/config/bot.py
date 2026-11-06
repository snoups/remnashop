import ipaddress
from urllib.parse import urlsplit

from loguru import logger
from pydantic import SecretStr, field_validator

from app.core.config.base import BaseConfig
from app.core.constants import API_V1, BOT_WEBHOOK_PATH


class BotConfig(BaseConfig, env_prefix="BOT_"):
    # token/secret_token are set in the dashboard (modules/settings/), not in env
    host: str = "0.0.0.0"
    port: int = 5001
    # a self-hosted telegram-bot-api server, if any
    api_url: str = "https://api.telegram.org"

    @field_validator("api_url")
    @classmethod
    def warn_on_plain_http(cls, value: str) -> str:
        # the token travels in the URL path: plain HTTP is fine only on the host's own network
        parts = urlsplit(value)
        if parts.scheme == "http" and not _is_local_host(parts.hostname or ""):
            logger.warning(
                f"BOT_API_URL '{value}' is plain HTTP to an outside host: "
                "the bot token goes over the network unencrypted"
            )
        return value

    @property
    def webhook_path(self) -> str:
        return f"{API_V1}{BOT_WEBHOOK_PATH}"

    def webhook_url(self, domain: SecretStr) -> SecretStr:
        return SecretStr(f"https://{domain.get_secret_value()}{self.webhook_path}")


def _is_local_host(host: str) -> bool:
    # a single-label name is a container on the compose network
    if "." not in host:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback
