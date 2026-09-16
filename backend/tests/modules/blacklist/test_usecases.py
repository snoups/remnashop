import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Role
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.modules.blacklist.dto import (
    AddBlacklistSourceDto,
    BlacklistEntryInputDto,
    ToggleBlacklistSourceDto,
)
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.blacklist.tasks import reconcile_blacklist_task
from app.modules.blacklist.usecases import (
    AddBlacklistEntryUseCase,
    AddBlacklistSourceUseCase,
    ListBlacklistUseCase,
    RemoveBlacklistEntryUseCase,
    ToggleBlacklistSourceUseCase,
)
from app.modules.users.dto import UserDto


@pytest.fixture
def owner() -> UserDto:
    return UserDto(id=1, telegram_id=1, name="owner", role=Role.OWNER)


@pytest.fixture
def plain_user() -> UserDto:
    return UserDto(id=2, telegram_id=2, name="user", role=Role.USER)


async def test_add_and_list_entry(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    owner: UserDto,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher)
    result = await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="id 55"))
    assert result.telegram_ids == [55]

    listed = await ListBlacklistUseCase(blacklist_repository, uow)(owner)
    assert listed.telegram_ids == [55]


async def test_remove_entry(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    owner: UserDto,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher)
    await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="55"))

    remove = RemoveBlacklistEntryUseCase(blacklist_repository, uow, event_publisher)
    result = await remove(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="55"))
    assert result.telegram_ids == []


async def test_add_entry_rejects_plain_user(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    plain_user: UserDto,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher)
    with pytest.raises(PermissionDeniedError):
        await add(plain_user, BlacklistEntryInputDto(kind=BlacklistKind.EMAIL, value="a@b.co"))


async def test_add_entry_rejects_invalid_value(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    owner: UserDto,
) -> None:
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher)
    with pytest.raises(ValidationError):
        await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="nope"))


async def test_add_entry_kicks_reconcile_only_for_a_real_new_entry(
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    owner: UserDto,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[None] = []

    async def _fake_kiq(**kwargs: object) -> None:
        calls.append(None)

    monkeypatch.setattr(reconcile_blacklist_task, "kiq", _fake_kiq)
    add = AddBlacklistEntryUseCase(blacklist_repository, uow, event_publisher)

    await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="77"))
    assert len(calls) == 1

    # duplicate -> add_entry is a no-op, no reconcile
    await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="77"))
    assert len(calls) == 1

    with pytest.raises(ValidationError):
        await add(owner, BlacklistEntryInputDto(kind=BlacklistKind.TELEGRAM_ID, value="nope"))
    assert len(calls) == 1


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
    toggled = await ToggleBlacklistSourceUseCase(blacklist_repository, uow)(
        owner, ToggleBlacklistSourceDto(source_id=src.id, enabled=False)
    )
    assert toggled.enabled is False
