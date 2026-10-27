import datetime
from typing import Optional

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.events import EventCategory
from app.core.exceptions import PermissionDeniedError
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.repository import EventLogRepository
from app.modules.event_log.usecases import (
    ClearNotificationsUseCase,
    GetNotificationsUseCase,
    MarkNotificationsReadUseCase,
)
from app.modules.notifications.dto import NOTIFICATION_GROUPS
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture
async def owner(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
        )
    return user


async def _log(
    repository: EventLogRepository,
    event_type: str,
    *,
    minutes_ago: int,
    actor_id: Optional[int] = None,
) -> None:
    await repository.create(
        EventLogEntryDto(
            category=EventCategory.AUTH,
            event_type=event_type,
            occurred_at=NOW - datetime.timedelta(minutes=minutes_ago),
            actor_id=actor_id,
            payload={},
        )
    )


async def test_notifications_keep_listed_types_newest_first_and_skip_own_actions(
    event_log_repository: EventLogRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    await _log(event_log_repository, "LoginFailedEvent", minutes_ago=10)
    await _log(event_log_repository, "LoginSucceededEvent", minutes_ago=5)  # not a notification
    await _log(event_log_repository, "BackupFailedEvent", minutes_ago=1)
    await _log(event_log_repository, "AdminCreatedEvent", minutes_ago=2, actor_id=owner.id)

    result = await GetNotificationsUseCase(event_log_repository, uow)(owner)

    assert [item.event_type for item in result.items] == ["BackupFailedEvent", "LoginFailedEvent"]
    assert result.unread_count == 2


async def test_unread_count_only_counts_events_after_seen_at(
    event_log_repository: EventLogRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    await _log(event_log_repository, "LoginFailedEvent", minutes_ago=10)
    await _log(event_log_repository, "BackupFailedEvent", minutes_ago=1)
    seen = owner.model_copy(update={"notifications_seen_at": NOW - datetime.timedelta(minutes=5)})

    result = await GetNotificationsUseCase(event_log_repository, uow)(seen)

    assert len(result.items) == 2
    assert result.unread_count == 1


async def test_admin_without_grant_cannot_get_notifications(
    event_log_repository: EventLogRepository, uow: UnitOfWork
) -> None:
    admin = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)

    with pytest.raises(PermissionDeniedError):
        await GetNotificationsUseCase(event_log_repository, uow)(admin)


async def test_mark_read_stores_seen_at(
    user_repository: UserRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    await MarkNotificationsReadUseCase(user_repository, uow)(owner)

    stored = await user_repository.find_by_id(owner.id)
    assert stored is not None
    assert stored.notifications_seen_at is not None


async def test_clear_hides_earlier_events_and_marks_them_read(
    event_log_repository: EventLogRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    owner: UserDto,
) -> None:
    await _log(event_log_repository, "LoginFailedEvent", minutes_ago=10)
    await ClearNotificationsUseCase(user_repository, uow)(owner)
    # module-level NOW can lag a long run by minutes, so stamp this one off the real clock
    after_clear = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=1)
    await event_log_repository.create(
        EventLogEntryDto(
            category=EventCategory.AUTH,
            event_type="BackupFailedEvent",
            occurred_at=after_clear,
            actor_id=None,
            payload={},
        )
    )

    cleared = await user_repository.find_by_id(owner.id)
    assert cleared is not None
    assert cleared.notifications_cleared_at is not None
    assert cleared.notifications_seen_at == cleared.notifications_cleared_at

    result = await GetNotificationsUseCase(event_log_repository, uow)(cleared)

    assert [item.event_type for item in result.items] == ["BackupFailedEvent"]
    assert result.unread_count == 1


async def test_notifications_follow_chosen_groups(
    event_log_repository: EventLogRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    await _log(event_log_repository, "LoginFailedEvent", minutes_ago=3)
    await _log(event_log_repository, "SubscriptionPurchasedEvent", minutes_ago=2)
    money_only = owner.model_copy(
        update={
            "notification_channels": {group: [] for group in NOTIFICATION_GROUPS}
            | {"money": ["bell"]}
        }
    )

    default = await GetNotificationsUseCase(event_log_repository, uow)(owner)
    chosen = await GetNotificationsUseCase(event_log_repository, uow)(money_only)

    # by default every group reaches the bell
    assert [item.event_type for item in default.items] == [
        "SubscriptionPurchasedEvent",
        "LoginFailedEvent",
    ]
    assert [item.event_type for item in chosen.items] == ["SubscriptionPurchasedEvent"]


async def test_bell_payload_drops_contact_fields_without_detail_permission(
    event_log_repository: EventLogRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    owner: UserDto,
) -> None:
    await event_log_repository.create(
        EventLogEntryDto(
            category=EventCategory.AUTH,
            event_type="LoginFailedEvent",
            occurred_at=NOW,
            actor_email="a@x.io",
            payload={
                "user": {
                    "login": "l",
                    "name": "n",
                    "username": "u",
                    "email": "e@x.io",
                    "telegram_id": 5,
                }
            },
        )
    )
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="adm",
                name="adm",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_grants=["NOTIFICATIONS_VIEW"],
            )
        )

    trimmed = (await GetNotificationsUseCase(event_log_repository, uow)(admin)).items[0]
    full = (await GetNotificationsUseCase(event_log_repository, uow)(owner)).items[0]

    assert trimmed.payload["user"] == {"login": "l", "name": "n"}
    assert trimmed.actor_email is None
    assert full.payload["user"]["email"] == "e@x.io"
    assert full.actor_email == "a@x.io"
