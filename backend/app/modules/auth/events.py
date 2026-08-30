from dataclasses import dataclass
from typing import ClassVar

from loguru import logger

from app.core.enums import OAuthProvider
from app.core.event_bus import EventBus
from app.core.events import ActorTargetEvent, BaseEvent, EventCategory, UserEvent


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


async def _log_owner_bootstrapped(event: OwnerBootstrappedEvent) -> None:
    logger.info(f"Owner bootstrapped: login='{event.user.login}'")


async def _log_login_succeeded(event: LoginSucceededEvent) -> None:
    logger.info(f"Successful login for login='{event.user.login}'")


async def _log_login_failed(event: LoginFailedEvent) -> None:
    logger.warning(f"Failed login attempt for login='{event.login}'")


async def _log_bootstrap_conflict(event: BootstrapConflictEvent) -> None:
    logger.warning(f"Bootstrap attempted with login='{event.login}' but an owner already exists")


async def _log_oauth_login_succeeded(event: OAuthLoginSucceededEvent) -> None:
    logger.info(f"Successful OAuth login via {event.provider} for login='{event.user.login}'")


async def _log_oauth_login_failed(event: OAuthLoginFailedEvent) -> None:
    logger.warning(f"Failed OAuth login attempt via {event.provider}")


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


async def _log_oauth_identity_connected(event: OAuthIdentityConnectedEvent) -> None:
    logger.info(f"OAuth identity connected: {event.provider} for login='{event.user.login}'")


async def _log_oauth_identity_disconnected(event: OAuthIdentityDisconnectedEvent) -> None:
    logger.info(f"OAuth identity disconnected: {event.provider} for login='{event.user.login}'")


async def _log_session_theft_detected(event: SessionTheftDetectedEvent) -> None:
    logger.warning(
        f"Refresh token reuse detected outside grace window: "
        f"user_id={event.user_id} session_id={event.session_id} -- session revoked"
    )


@dataclass(frozen=True, kw_only=True)
class SessionRevokedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    session_id: int


async def _log_session_revoked(event: SessionRevokedEvent) -> None:
    logger.info(f"Session {event.session_id} revoked for login='{event.user.login}'")


@dataclass(frozen=True, kw_only=True)
class UserSessionRevokedByAdminEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    session_id: int


async def _log_user_session_revoked_by_admin(event: UserSessionRevokedByAdminEvent) -> None:
    logger.info(
        f"Session {event.session_id} of login='{event.target.login}' "
        f"revoked by login='{event.actor.login}'"
    )


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
