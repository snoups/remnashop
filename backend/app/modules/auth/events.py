from dataclasses import dataclass
from typing import ClassVar

from loguru import logger

from app.core.enums import OAuthProvider
from app.core.event_bus import EventBus
from app.core.events import ActorTargetEvent, BaseEvent, EventCategory, StoredEvent, UserEvent
from app.modules.settings.events import OidcIssuerChangedEvent


@dataclass(frozen=True, kw_only=True)
class OwnerBootstrappedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH


@dataclass(frozen=True, kw_only=True)
class LoginSucceededEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH


@dataclass(frozen=True, kw_only=True)
class LoginFailedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    login: str


@dataclass(frozen=True, kw_only=True)
class BootstrapConflictEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    login: str


@dataclass(frozen=True, kw_only=True)
class OAuthLoginSucceededEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class OAuthLoginFailedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


async def _log_owner_bootstrapped(entry: StoredEvent) -> None:
    logger.info(f"Owner bootstrapped: login='{entry.payload['user']['login']}'")


async def _log_login_succeeded(entry: StoredEvent) -> None:
    logger.info(f"Successful login for login='{entry.payload['user']['login']}'")


async def _log_login_failed(entry: StoredEvent) -> None:
    logger.warning(f"Failed login attempt for login='{entry.payload['login']}'")


async def _log_bootstrap_conflict(entry: StoredEvent) -> None:
    logger.warning(
        f"Bootstrap attempted with login='{entry.payload['login']}' but an owner already exists"
    )


async def _log_oauth_login_succeeded(entry: StoredEvent) -> None:
    logger.info(
        f"Successful OAuth login via {entry.payload['provider']} "
        f"for login='{entry.payload['user']['login']}'"
    )


async def _log_oauth_login_failed(entry: StoredEvent) -> None:
    logger.warning(f"Failed OAuth login attempt via {entry.payload['provider']}")


@dataclass(frozen=True, kw_only=True)
class OAuthIdentityConnectedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class OAuthIdentityDisconnectedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    provider: OAuthProvider


@dataclass(frozen=True, kw_only=True)
class SessionTheftDetectedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    user_id: int
    session_id: int


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


async def _log_session_theft_detected(entry: StoredEvent) -> None:
    logger.warning(
        f"Refresh token reuse detected outside grace window: "
        f"user_id={entry.payload['user_id']} session_id={entry.payload['session_id']} "
        "-- session revoked"
    )


@dataclass(frozen=True, kw_only=True)
class SessionRevokedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    session_id: int


async def _log_session_revoked(entry: StoredEvent) -> None:
    logger.info(
        f"Session {entry.payload['session_id']} revoked "
        f"for login='{entry.payload['user']['login']}'"
    )


@dataclass(frozen=True, kw_only=True)
class UserSessionRevokedByAdminEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    session_id: int


async def _log_user_session_revoked_by_admin(entry: StoredEvent) -> None:
    logger.info(
        f"Session {entry.payload['session_id']} of login='{entry.payload['target']['login']}' "
        f"revoked by login='{entry.payload['actor']['login']}'"
    )


async def _on_oidc_issuer_changed(entry: StoredEvent) -> None:
    # Deferred: app.modules.auth.tasks imports app.worker.broker, a
    # module-level singleton that must not load into the api/telegram
    # processes -- this module is imported eagerly by login.py and friends
    # there, unlike this handler, which only runs in the worker process.
    from app.modules.auth.tasks import cleanup_oidc_identities_task  # noqa: PLC0415

    await cleanup_oidc_identities_task.kiq()  # type: ignore[call-overload]


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(OwnerBootstrappedEvent, _log_owner_bootstrapped)
    bus.subscribe(LoginSucceededEvent, _log_login_succeeded)
    bus.subscribe(LoginFailedEvent, _log_login_failed)
    bus.subscribe(BootstrapConflictEvent, _log_bootstrap_conflict)
    bus.subscribe(OAuthLoginSucceededEvent, _log_oauth_login_succeeded)
    bus.subscribe(OAuthLoginFailedEvent, _log_oauth_login_failed)
    bus.subscribe(OAuthIdentityConnectedEvent, _log_oauth_identity_connected)
    bus.subscribe(OAuthIdentityDisconnectedEvent, _log_oauth_identity_disconnected)
    bus.subscribe(SessionTheftDetectedEvent, _log_session_theft_detected)
    bus.subscribe(SessionRevokedEvent, _log_session_revoked)
    bus.subscribe(UserSessionRevokedByAdminEvent, _log_user_session_revoked_by_admin)
    bus.subscribe(OidcIssuerChangedEvent, _on_oidc_issuer_changed)
