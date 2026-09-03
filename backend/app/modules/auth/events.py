from dataclasses import dataclass
from typing import ClassVar

from loguru import logger

from app.core.event_bus import EventBus
from app.core.events import ActorTargetEvent, BaseEvent, EventCategory, StoredEvent, UserEvent


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


@dataclass(frozen=True, kw_only=True)
class SessionTheftDetectedEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH
    user_id: int
    session_id: int


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


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(OwnerBootstrappedEvent, _log_owner_bootstrapped)
    bus.subscribe(LoginSucceededEvent, _log_login_succeeded)
    bus.subscribe(LoginFailedEvent, _log_login_failed)
    bus.subscribe(BootstrapConflictEvent, _log_bootstrap_conflict)
    bus.subscribe(SessionTheftDetectedEvent, _log_session_theft_detected)
    bus.subscribe(SessionRevokedEvent, _log_session_revoked)
    bus.subscribe(UserSessionRevokedByAdminEvent, _log_user_session_revoked_by_admin)
