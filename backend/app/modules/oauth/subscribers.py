from loguru import logger

from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.oauth.events import (
    OAuthIdentityConnectedEvent,
    OAuthIdentityDisconnectedEvent,
    OAuthLoginFailedEvent,
    OAuthLoginSucceededEvent,
)


async def _log_oauth_login_succeeded(entry: StoredEvent) -> None:
    logger.info(
        f"Successful OAuth login via {entry.payload['provider']} "
        f"for login='{entry.payload['user']['login']}'"
    )


async def _log_oauth_login_failed(entry: StoredEvent) -> None:
    logger.warning(f"Failed OAuth login attempt via {entry.payload['provider']}")


async def _log_oauth_identity_connected(entry: StoredEvent) -> None:
    logger.info(
        f"OAuth identity connected: {entry.payload['provider']} "
        f"for login='{entry.payload['user']['login']}'"
    )


async def _log_oauth_identity_disconnected(entry: StoredEvent) -> None:
    logger.info(
        f"OAuth identity disconnected: {entry.payload['provider']} "
        f"for login='{entry.payload['user']['login']}'"
    )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(OAuthLoginSucceededEvent, _log_oauth_login_succeeded)
    bus.subscribe(OAuthLoginFailedEvent, _log_oauth_login_failed)
    bus.subscribe(OAuthIdentityConnectedEvent, _log_oauth_identity_connected)
    bus.subscribe(OAuthIdentityDisconnectedEvent, _log_oauth_identity_disconnected)
