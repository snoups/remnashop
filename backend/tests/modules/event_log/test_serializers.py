from dataclasses import dataclass
from typing import ClassVar

from app.core.enums import Locale, Role
from app.core.events import ActorTargetEvent, EventCategory
from app.modules.auth.events import LoginFailedEvent, LoginSucceededEvent
from app.modules.event_log.serializers import build_payload
from app.modules.users.dto import UserDto
from app.modules.users.events import AdminCreatedEvent, AdminPermissionsUpdatedEvent

OWNER = UserDto(
    id=1,
    login="owner",
    name="owner",
    role=Role.OWNER,
    language=Locale.EN,
    password_hash="super-secret-hash",
)
ADMIN = UserDto(
    id=2,
    login="admin",
    name="admin",
    role=Role.ADMIN,
    language=Locale.EN,
    password_hash="another-secret-hash",
    permission_grants=["BOT_SETTINGS_MANAGE"],
    ip_allowlist=["10.0.0.1"],
)


def test_actor_target_event_payload_never_contains_password_hash() -> None:
    event = AdminCreatedEvent(actor=OWNER, target=ADMIN)
    payload = build_payload(event)

    serialized = str(payload)
    assert "super-secret-hash" not in serialized
    assert "another-secret-hash" not in serialized


def test_actor_target_event_payload_never_contains_permission_or_ip_fields() -> None:
    event = AdminCreatedEvent(actor=OWNER, target=ADMIN)
    payload = build_payload(event)

    assert "permission_grants" not in payload.get("target", {})
    assert "ip_allowlist" not in payload.get("target", {})


def test_admin_created_payload_shape() -> None:
    event = AdminCreatedEvent(actor=OWNER, target=ADMIN)
    payload = build_payload(event)

    assert payload["target"]["id"] == ADMIN.id
    assert payload["target"]["login"] == "admin"
    assert payload["target"]["role"] == "ADMIN"


def test_admin_permissions_updated_payload_includes_grants_and_revokes() -> None:
    event = AdminPermissionsUpdatedEvent(
        actor=OWNER, target=ADMIN, permission_grants=["BOT_SETTINGS_MANAGE"], permission_revokes=[]
    )
    payload = build_payload(event)

    assert payload["permission_grants"] == ["BOT_SETTINGS_MANAGE"]
    assert payload["permission_revokes"] == []


def test_user_event_payload_shape() -> None:
    event = LoginSucceededEvent(user=OWNER)
    payload = build_payload(event)

    assert payload["user"]["login"] == "owner"
    assert "password_hash" not in str(payload)


def test_plain_event_with_extra_field_payload_shape() -> None:
    event = LoginFailedEvent(login="someone")
    payload = build_payload(event)

    assert payload["login"] == "someone"


@dataclass(frozen=True, kw_only=True)
class _HypotheticalEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT
    other_user: UserDto


def test_user_dto_field_under_unknown_name_is_still_sanitized() -> None:
    secret_user = UserDto(
        id=3,
        login="secret",
        name="secret",
        role=Role.ADMIN,
        language=Locale.EN,
        password_hash="LEAKED-HASH",
        permission_grants=["BOT_SETTINGS_MANAGE"],
        ip_allowlist=["10.0.0.2"],
    )
    event = _HypotheticalEvent(actor=OWNER, target=ADMIN, other_user=secret_user)
    payload = build_payload(event)

    assert "LEAKED-HASH" not in str(payload)
    assert "permission_grants" not in payload["other_user"]
    assert "ip_allowlist" not in payload["other_user"]
    assert payload["other_user"]["login"] == "secret"
