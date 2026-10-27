import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.exceptions import ValidationError
from app.modules.notifications import bell_event_types
from app.modules.notifications.dto import (
    DEFAULT_NOTIFICATION_CHANNELS,
    NOTIFICATION_GROUPS,
    NotificationChannel,
    UpdateNotificationChannelsDto,
    channels_for,
    group_of,
)
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.usecases import (
    GetNotificationChannelsUseCase,
    UpdateNotificationChannelsUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
async def owner(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    async with uow:
        return await user_repository.create(
            CreateUserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
        )


def test_defaults_send_critical_groups_everywhere_and_the_rest_to_the_bell(
    owner: UserDto,
) -> None:
    every = {NotificationChannel.BELL, NotificationChannel.PUSH, NotificationChannel.TELEGRAM}
    assert channels_for(owner, "security") == every
    assert channels_for(owner, "failures") == every
    assert channels_for(owner, "infrastructure") == every
    assert channels_for(owner, "customers") == {NotificationChannel.BELL}
    assert channels_for(owner, "money") == {NotificationChannel.BELL}
    assert channels_for(owner, "unknown-group") == frozenset()


def test_stored_matrix_overrides_defaults_and_drops_unknown_channels(owner: UserDto) -> None:
    user = owner.model_copy(
        update={"notification_channels": {"money": ["push", "fax"], "security": []}}
    )
    assert channels_for(user, "money") == {NotificationChannel.PUSH}
    assert channels_for(user, "security") == frozenset()
    # a group the stored matrix predates gets the default, not nothing
    assert channels_for(user, "failures") == DEFAULT_NOTIFICATION_CHANNELS["failures"]


def test_bell_event_types_follow_the_bell_column(owner: UserDto) -> None:
    matrix = {group: [] for group in NOTIFICATION_GROUPS} | {"failures": ["bell"]}
    user = owner.model_copy(update={"notification_channels": matrix})
    assert bell_event_types(user) == NOTIFICATION_GROUPS["failures"]


def test_group_of_maps_event_types() -> None:
    assert group_of("LoginFailedEvent") == "security"
    assert group_of("LoginSucceededEvent") is None


async def test_update_stores_matrix_and_get_reads_it(
    owner: UserDto,
    user_repository: UserRepository,
    uow: UnitOfWork,
    notification_repository: NotificationRepository,
) -> None:
    update = UpdateNotificationChannelsUseCase(user_repository, notification_repository, uow)
    result = await update(
        owner,
        UpdateNotificationChannelsDto(channels={"money": ["push", "bell"], "security": ["bell"]}),
    )

    assert result.channels["money"] == ["bell", "push"]
    assert result.channels["failures"] == []
    assert result.is_push_configured is False
    assert result.telegram_available is False
    stored = await user_repository.find_by_id(owner.id)
    assert stored is not None
    get = GetNotificationChannelsUseCase(notification_repository, uow)
    assert (await get(stored, None)).channels["security"] == ["bell"]


@pytest.mark.parametrize("matrix", [{"nope": ["bell"]}, {"money": ["fax"]}])
async def test_update_rejects_unknown_groups_and_channels(
    owner: UserDto,
    user_repository: UserRepository,
    uow: UnitOfWork,
    notification_repository: NotificationRepository,
    matrix: dict[str, list[str]],
) -> None:
    update = UpdateNotificationChannelsUseCase(user_repository, notification_repository, uow)
    with pytest.raises(ValidationError):
        await update(owner, UpdateNotificationChannelsDto(channels=matrix))
