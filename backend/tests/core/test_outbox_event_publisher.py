from dataclasses import dataclass
from typing import ClassVar

import pytest
from sqlalchemy import func, select

from app.core.actor import SyntheticActor
from app.core.db.models import EventOutboxEntry, User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.events import ActorTargetEvent, BaseEvent, EventCategory
from app.core.outbox_event_publisher import OutboxEventPublisher
from app.modules.auth.events import LoginFailedEvent, LoginSucceededEvent
from app.modules.users.dto import UserDto
from app.modules.users.events import AdminCreatedEvent, AdminPermissionsUpdatedEvent
from tests.fakes.dispatch import RecordingDispatch

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


@pytest.fixture(autouse=True)
async def _seed_owner_row(session) -> None:
    # event_outbox.actor_id is a real FK, so OWNER needs a row
    session.add(
        User(
            id=OWNER.id,
            login=OWNER.login,
            name=OWNER.name,
            role=OWNER.role,
            language=OWNER.language,
            is_blocked=False,
        )
    )
    await session.flush()


async def _published_row(session, event: BaseEvent) -> EventOutboxEntry:
    publisher = OutboxEventPublisher(UnitOfWork(session), RecordingDispatch())
    await publisher.publish(event)
    row = (await session.scalars(select(EventOutboxEntry))).one()
    return row


async def test_actor_target_event_payload_never_contains_password_hash(session) -> None:
    row = await _published_row(session, AdminCreatedEvent(actor=OWNER, target=ADMIN))
    serialized = str(row.payload)
    assert "super-secret-hash" not in serialized
    assert "another-secret-hash" not in serialized


async def test_actor_target_event_payload_never_contains_permission_or_ip_fields(session) -> None:
    row = await _published_row(session, AdminCreatedEvent(actor=OWNER, target=ADMIN))
    assert "permission_grants" not in row.payload.get("target", {})
    assert "ip_allowlist" not in row.payload.get("target", {})


async def test_admin_created_payload_shape(session) -> None:
    row = await _published_row(session, AdminCreatedEvent(actor=OWNER, target=ADMIN))
    assert row.payload["target"]["id"] == ADMIN.id
    assert row.payload["target"]["login"] == "admin"
    assert row.payload["target"]["role"] == "ADMIN"


async def test_user_snapshot_includes_contact_fields(session) -> None:
    target = ADMIN.model_copy(
        update={"telegram_id": 123456789, "username": "admin_tg", "email": "admin@example.com"}
    )
    row = await _published_row(session, AdminCreatedEvent(actor=OWNER, target=target))
    assert row.payload["target"]["telegram_id"] == 123456789
    assert row.payload["target"]["username"] == "admin_tg"
    assert row.payload["target"]["email"] == "admin@example.com"


async def test_admin_permissions_updated_payload_includes_grants_and_revokes(session) -> None:
    event = AdminPermissionsUpdatedEvent(
        actor=OWNER, target=ADMIN, permission_grants=["BOT_SETTINGS_MANAGE"], permission_revokes=[]
    )
    row = await _published_row(session, event)
    assert row.payload["permission_grants"] == ["BOT_SETTINGS_MANAGE"]
    assert row.payload["permission_revokes"] == []


async def test_user_event_payload_shape(session) -> None:
    row = await _published_row(session, LoginSucceededEvent(user=OWNER))
    assert row.payload["user"]["login"] == "owner"
    assert "password_hash" not in str(row.payload)


async def test_plain_event_with_extra_field_payload_shape(session) -> None:
    row = await _published_row(session, LoginFailedEvent(login="someone"))
    assert row.payload["login"] == "someone"


@dataclass(frozen=True, kw_only=True)
class _HypotheticalEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.ADMIN_MANAGEMENT
    other_user: UserDto


async def test_user_dto_field_under_unknown_name_is_still_sanitized(session) -> None:
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
    row = await _published_row(session, event)
    assert "LEAKED-HASH" not in str(row.payload)
    assert "permission_grants" not in row.payload["other_user"]
    assert "ip_allowlist" not in row.payload["other_user"]
    assert row.payload["other_user"]["login"] == "secret"


async def test_publish_records_event_type_and_category(session) -> None:
    row = await _published_row(session, LoginSucceededEvent(user=OWNER))
    assert row.event_type == "LoginSucceededEvent"
    assert row.category == EventCategory.AUTH


async def test_publish_records_user_event_actor(session) -> None:
    row = await _published_row(session, LoginSucceededEvent(user=OWNER))
    assert row.actor_id == OWNER.id
    assert row.actor_login == OWNER.login


async def test_publish_drops_api_token_actor_id(session) -> None:
    api_token_actor = UserDto(id=0, name="API Token: ci", role=Role.USER, language=Locale.EN)
    row = await _published_row(session, AdminCreatedEvent(actor=api_token_actor, target=ADMIN))
    assert row.actor_id is None
    assert row.actor_name == "API Token: ci"


async def test_publish_handles_synthetic_actor(session) -> None:
    token_actor = SyntheticActor(
        id=0,
        role=Role.USER,
        name="API Token: ci",
        is_privileged=True,
        log="[api_token:ci]",
    )
    row = await _published_row(session, AdminCreatedEvent(actor=token_actor, target=ADMIN))
    assert row.actor_id is None
    assert row.actor_name == "API Token: ci"
    assert row.actor_login is None


async def test_publish_drops_system_actor_id(session) -> None:
    system_actor = UserDto(id=-1, name="SYSTEM", role=Role.SYSTEM, language=Locale.EN)
    row = await _published_row(session, AdminCreatedEvent(actor=system_actor, target=ADMIN))
    assert row.actor_id is None
    assert row.actor_name == "SYSTEM"


async def test_publish_writes_inside_the_callers_transaction_not_committed_separately(
    session,
) -> None:
    # visible in the same transaction without a commit: publish() joins the
    # caller's transaction
    publisher = OutboxEventPublisher(UnitOfWork(session), RecordingDispatch())
    await publisher.publish(LoginSucceededEvent(user=OWNER))
    count = await session.scalar(select(func.count()).select_from(EventOutboxEntry))
    assert count == 1

    await session.rollback()
    count = await session.scalar(select(func.count()).select_from(EventOutboxEntry))
    assert count == 0


async def test_publish_kicks_the_worker_only_once_the_transaction_commits(session) -> None:
    uow = UnitOfWork(session)
    dispatch = RecordingDispatch()
    publisher = OutboxEventPublisher(uow, dispatch)

    async with uow:
        await publisher.publish(LoginSucceededEvent(user=OWNER))
        assert dispatch.messages == []

    row = (await session.scalars(select(EventOutboxEntry))).one()
    assert dispatch.messages == [{"outbox_id": row.id}]


async def test_publish_never_kicks_for_a_rolled_back_transaction(session) -> None:
    uow = UnitOfWork(session)
    dispatch = RecordingDispatch()
    publisher = OutboxEventPublisher(uow, dispatch)

    with pytest.raises(RuntimeError):
        async with uow:
            await publisher.publish(LoginSucceededEvent(user=OWNER))
            raise RuntimeError("abort")

    assert dispatch.messages == []
