from app.core.enums import Locale, Role
from app.core.events import EventCategory
from app.modules.users.dto import UserDto
from app.modules.users.events import (
    AdminCreatedEvent,
    AdminDeletedEvent,
    AdminDemotedEvent,
    AdminPermissionsUpdatedEvent,
    AdminPromotedEvent,
    TelegramUserRegisteredEvent,
    UserDeletedEvent,
)

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
ADMIN = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)
CUSTOMER = UserDto(id=3, telegram_id=42, name="customer", role=Role.USER, language=Locale.EN)


def test_admin_created_event() -> None:
    event = AdminCreatedEvent(actor=OWNER, target=ADMIN)
    assert event.category == EventCategory.ADMIN_MANAGEMENT
    assert event.actor is OWNER
    assert event.target is ADMIN


def test_admin_promoted_event() -> None:
    event = AdminPromotedEvent(actor=OWNER, target=ADMIN)
    assert event.category == EventCategory.ADMIN_MANAGEMENT


def test_admin_demoted_event() -> None:
    event = AdminDemotedEvent(actor=OWNER, target=ADMIN)
    assert event.category == EventCategory.ADMIN_MANAGEMENT


def test_admin_permissions_updated_event_carries_grants_and_revokes() -> None:
    event = AdminPermissionsUpdatedEvent(
        actor=OWNER,
        target=ADMIN,
        permission_grants=["BOT_SETTINGS_MANAGE"],
        permission_revokes=["OAUTH_SETTINGS_MANAGE"],
    )
    assert event.category == EventCategory.ADMIN_MANAGEMENT
    assert event.permission_grants == ["BOT_SETTINGS_MANAGE"]
    assert event.permission_revokes == ["OAUTH_SETTINGS_MANAGE"]


def test_telegram_user_registered_event() -> None:
    event = TelegramUserRegisteredEvent(user=CUSTOMER)
    assert event.category == EventCategory.USER
    assert event.user is CUSTOMER


def test_admin_deleted_event() -> None:
    event = AdminDeletedEvent(actor=OWNER, target=ADMIN)
    assert event.category == EventCategory.ADMIN_MANAGEMENT
    assert event.actor is OWNER
    assert event.target is ADMIN


def test_user_deleted_event() -> None:
    event = UserDeletedEvent(actor=OWNER, target=CUSTOMER)
    assert event.category == EventCategory.USER
    assert event.actor is OWNER
    assert event.target is CUSTOMER
