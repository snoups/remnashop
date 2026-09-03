from dataclasses import dataclass
from typing import ClassVar

from loguru import logger

from app.core.enums import OAuthProvider
from app.core.event_bus import EventBus
from app.core.events import BaseEvent, EventCategory, StoredEvent, UserEvent
from app.modules.settings.events import OidcIssuerChangedEvent


@dataclass(frozen=True, kw_only=True)
class OAuthLoginSucceededEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class OAuthLoginFailedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class OAuthIdentityConnectedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class OAuthIdentityDisconnectedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


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


async def _on_oidc_issuer_changed(entry: StoredEvent) -> None:
    # Deferred: app.modules.oauth.tasks imports app.worker.broker, a
    # module-level singleton that must not load into the api/telegram
    # processes -- this module is imported eagerly by oauth_login_callback.py
    # and friends there, unlike this handler, which only runs in the worker
    # process.
    from app.modules.oauth.tasks import cleanup_oidc_identities_task  # noqa: PLC0415

    await cleanup_oidc_identities_task.kiq()  # type: ignore[call-overload]


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(OAuthLoginSucceededEvent, _log_oauth_login_succeeded)
    bus.subscribe(OAuthLoginFailedEvent, _log_oauth_login_failed)
    bus.subscribe(OAuthIdentityConnectedEvent, _log_oauth_identity_connected)
    bus.subscribe(OAuthIdentityDisconnectedEvent, _log_oauth_identity_disconnected)
    bus.subscribe(OidcIssuerChangedEvent, _on_oidc_issuer_changed)
