import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Locale, Role
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.modules.blacklist.dto import (
    AddBlacklistSourceDto,
    BlacklistEntryInputDto,
    UpdateBlacklistSourceDto,
)
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.blacklist.usecases import (
    AddBlacklistEntryUseCase,
    AddBlacklistSourceUseCase,
    GetBlacklistSourceUseCase,
    ListBlacklistUseCase,
    RemoveBlacklistEntryUseCase,
    UpdateBlacklistSourceUseCase,
)
from app.modules.users.dto import UserDto
from tests.fakes.dispatch import RecordingDispatch


@pytest.fixture
def reconcile() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def owner() -> UserDto:
    return UserDto(id=1, telegram_id=1, name="owner", role=Role.OWNER)


@pytest.fixture
def plain_user() -> UserDto:
    return UserDto(id=2, telegram_id=2, name="user", role=Role.USER)


@pytest.fixture(autouse=True)
async def _seed_actor_rows(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK, and the actor DTOs above have no rows
    for user_id in (1, 2):
        session.add(
            User(
                id=user_id,
                name=f"u{user_id}",
                telegram_id=user_id,
                role=Role.USER,
                language=Locale.EN,
                is_blocked=False,
            )
        )
    await session.flush()


async def test_add_and_list_entry(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    owner: UserDto,
    reconcile: RecordingDispatch,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher, reconcile)
    result = await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="55"))
    assert result.telegram_ids == [55]

    listed = await ListBlacklistUseCase(blacklist_repository, uow)(owner)
    assert listed.telegram_ids == [55]


async def test_remove_entry(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    owner: UserDto,
    reconcile: RecordingDispatch,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher, reconcile)
    await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="55"))

    remove = RemoveBlacklistEntryUseCase(blacklist_repository, uow, event_publisher)
    result = await remove(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="55"))
    assert result.telegram_ids == []


async def test_add_entry_rejects_plain_user(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    plain_user: UserDto,
    reconcile: RecordingDispatch,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher, reconcile)
    with pytest.raises(PermissionDeniedError):
        await add(plain_user, BlacklistEntryInputDto(kind=BlacklistKind.EMAIL, value="a@b.co"))


async def test_add_entry_rejects_invalid_value(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    owner: UserDto,
    reconcile: RecordingDispatch,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher, reconcile)
    with pytest.raises(ValidationError):
        await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="nope"))
    with pytest.raises(ValidationError):
        await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="9" * 20))


async def test_add_entry_kicks_reconcile_only_for_a_real_new_entry(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    owner: UserDto,
    reconcile: RecordingDispatch,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher, reconcile)

    await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="77"))
    assert len(reconcile.messages) == 1

    # duplicate -> add_entry is a no-op, no reconcile
    await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="77"))
    assert len(reconcile.messages) == 1

    with pytest.raises(ValidationError):
        await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="nope"))
    assert len(reconcile.messages) == 1


async def test_add_source_rejects_non_https(
    blacklist_repository: BlacklistRepository, uow: UnitOfWork, owner: UserDto
) -> None:
    add = AddBlacklistSourceUseCase(blacklist_repository, uow)
    with pytest.raises(ValidationError):
        await add(owner, AddBlacklistSourceDto(url="http://insecure.example/list.txt"))


async def test_toggle_source(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    owner: UserDto,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        "app.modules.blacklist.usecases.add_blacklist_source.assert_public_https_host",
        _fake_assert_public_https_host,
    )

    src = await AddBlacklistSourceUseCase(blacklist_repository, uow)(
        owner, AddBlacklistSourceDto(url="https://ok.example/list.txt")
    )
    toggled = await UpdateBlacklistSourceUseCase(blacklist_repository, uow)(
        owner, UpdateBlacklistSourceDto(source_id=src.id, enabled=False)
    )
    assert toggled.enabled is False


async def test_add_source_derives_name_when_blank(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    owner: UserDto,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        "app.modules.blacklist.usecases.add_blacklist_source.assert_public_https_host",
        _fake_assert_public_https_host,
    )
    add = AddBlacklistSourceUseCase(blacklist_repository, uow)

    derived = await add(owner, AddBlacklistSourceDto(url="https://feed.example/a.txt", name="  "))
    assert derived.name == "feed.example/a.txt"

    explicit = await add(
        owner, AddBlacklistSourceDto(url="https://feed.example/b.txt", name=" Mine ")
    )
    assert explicit.name == "Mine"


async def test_get_source_requires_its_own_permission(
    blacklist_repository: BlacklistRepository, uow: UnitOfWork, plain_user: UserDto
) -> None:
    with pytest.raises(PermissionDeniedError):
        await GetBlacklistSourceUseCase(blacklist_repository, uow)(plain_user, 1)
