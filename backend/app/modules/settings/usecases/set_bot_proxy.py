from typing import Final
from urllib.parse import urlsplit

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import BotSettingsDto, SetBotProxyDto
from app.modules.settings.events import BotSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository

# What aiohttp-socks accepts: the bot's aiogram session and core.telegram_api. python-socks
# has no https and doesn't know socks5h, but it resolves DNS on the proxy side
# for socks5 anyway, so it's the same thing.
_PROXY_SCHEMES: Final[dict[str, str]] = {
    "http": "http",
    "socks5": "socks5",
    "socks5h": "socks5",
}


def normalize_proxy_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        has_port = parts.port is not None
    except ValueError:  # malformed IPv6 host, non-numeric or out-of-range port
        pass
    else:
        scheme = _PROXY_SCHEMES.get(parts.scheme.lower())
        if scheme is not None and parts.hostname and has_port:
            return parts._replace(scheme=scheme, path="", query="", fragment="").geturl()
    raise ValidationError(
        "Proxy URL must look like scheme://[user:password@]host:port "
        f"with scheme one of: {', '.join(_PROXY_SCHEMES)}",
        code=ErrorCode.BOT_PROXY_URL_INVALID,
    )


class SetBotProxyUseCase(UseCase[SetBotProxyDto, BotSettingsDto]):
    required_permission = Permission.BOT_PROXY_SET

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SetBotProxyDto) -> BotSettingsDto:
        proxy_url = normalize_proxy_url(data.proxy_url)
        async with self._uow:
            settings = await self._settings_repository.set_bot_proxy_url(proxy_url)
            await self._event_publisher.publish(
                BotSettingsChangedEvent(actor=actor, action="proxy_set")
            )
        logger.info(f"{actor.log} Set the bot proxy")
        return settings
