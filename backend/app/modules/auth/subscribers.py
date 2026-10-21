from loguru import logger

from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.auth.events import (
    BootstrapConflictEvent,
    LoginFailedEvent,
    LoginSucceededEvent,
    OwnerBootstrappedEvent,
    SessionRevokedEvent,
    SessionTheftDetectedEvent,
    UserSessionRevokedByAdminEvent,
)


async def _log_owner_bootstrapped(event: OwnerBootstrappedEvent, entry: StoredEvent) -> None:
    logger.info(f"Owner bootstrapped: login='{event.user.login}'")


async def _log_login_succeeded(event: LoginSucceededEvent, entry: StoredEvent) -> None:
    logger.info(f"Successful login for login='{event.user.login}'")


async def _log_login_failed(event: LoginFailedEvent, entry: StoredEvent) -> None:
    logger.warning(f"Failed login attempt for login='{event.login}'")


async def _log_bootstrap_conflict(event: BootstrapConflictEvent, entry: StoredEvent) -> None:
    logger.warning(f"Bootstrap attempted with login='{event.login}' but an owner already exists")


async def _log_session_theft_detected(event: SessionTheftDetectedEvent, entry: StoredEvent) -> None:
    logger.warning(
        f"Refresh token reuse detected outside grace window: "
        f"user_id={event.user_id} session_id={event.session_id} "
        "-- session revoked"
    )


async def _log_session_revoked(event: SessionRevokedEvent, entry: StoredEvent) -> None:
    logger.info(f"Session {event.session_id} revoked for login='{event.user.login}'")


async def _log_user_session_revoked_by_admin(
    event: UserSessionRevokedByAdminEvent, entry: StoredEvent
) -> None:
    logger.info(
        f"Session {event.session_id} of login='{event.target.login}' "
        f"revoked by login='{event.actor.login}'"
    )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(OwnerBootstrappedEvent, _log_owner_bootstrapped)
    bus.subscribe(LoginSucceededEvent, _log_login_succeeded)
    bus.subscribe(LoginFailedEvent, _log_login_failed)
    bus.subscribe(BootstrapConflictEvent, _log_bootstrap_conflict)
    bus.subscribe(SessionTheftDetectedEvent, _log_session_theft_detected)
    bus.subscribe(SessionRevokedEvent, _log_session_revoked)
    bus.subscribe(UserSessionRevokedByAdminEvent, _log_user_session_revoked_by_admin)
