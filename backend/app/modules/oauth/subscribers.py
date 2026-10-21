from loguru import logger

from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.oauth.events import (
    OAuthIdentityConnectedEvent,
    OAuthIdentityDisconnectedEvent,
    OAuthLoginFailedEvent,
    OAuthLoginSucceededEvent,
)


async def _log_oauth_login_succeeded(event: OAuthLoginSucceededEvent, entry: StoredEvent) -> None:
    logger.info(f"Successful OAuth login via {event.provider} for login='{event.user.login}'")


async def _log_oauth_login_failed(event: OAuthLoginFailedEvent, entry: StoredEvent) -> None:
    logger.warning(f"Failed OAuth login attempt via {event.provider}")


async def _log_oauth_identity_connected(
    event: OAuthIdentityConnectedEvent, entry: StoredEvent
) -> None:
    logger.info(f"OAuth identity connected: {event.provider} for login='{event.user.login}'")


async def _log_oauth_identity_disconnected(
    event: OAuthIdentityDisconnectedEvent, entry: StoredEvent
) -> None:
    logger.info(f"OAuth identity disconnected: {event.provider} for login='{event.user.login}'")


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(OAuthLoginSucceededEvent, _log_oauth_login_succeeded)
    bus.subscribe(OAuthLoginFailedEvent, _log_oauth_login_failed)
    bus.subscribe(OAuthIdentityConnectedEvent, _log_oauth_identity_connected)
    bus.subscribe(OAuthIdentityDisconnectedEvent, _log_oauth_identity_disconnected)
