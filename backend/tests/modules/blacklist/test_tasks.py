from app.core.enums import BlacklistKind, Role
from app.modules.blacklist import BlacklistRepository
from app.modules.blacklist.dto import AddBlacklistSourceDto, ParsedSourceList
from app.modules.blacklist.tasks import reconcile_blacklist, sync_blacklist_sources
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_reconcile_blocks_matching_user_and_does_not_unblock(
    blacklist_repository: BlacklistRepository,
    user_repository: UserRepository,
    uow,
    event_publisher,
) -> None:
    user = await user_repository.create(CreateUserDto(telegram_id=777, name="x"))
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "777")

    await reconcile_blacklist(blacklist_repository, user_repository, uow, event_publisher)
    refetched = await user_repository.get_by_id(user.id)
    assert refetched is not None and refetched.is_blocked is True

    # entry removed -> reconcile must NOT unblock
    await blacklist_repository.remove_entry(BlacklistKind.TELEGRAM_ID, "777")
    await reconcile_blacklist(blacklist_repository, user_repository, uow, event_publisher)
    refetched = await user_repository.get_by_id(user.id)
    assert refetched is not None and refetched.is_blocked is True


async def test_reconcile_never_blocks_staff(
    blacklist_repository: BlacklistRepository,
    user_repository: UserRepository,
    uow,
    event_publisher,
) -> None:
    owner = await user_repository.create(
        CreateUserDto(telegram_id=111, name="owner", role=Role.OWNER)
    )
    plain = await user_repository.create(CreateUserDto(telegram_id=222, name="plain"))
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "111")
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "222")

    await reconcile_blacklist(blacklist_repository, user_repository, uow, event_publisher)

    refetched_owner = await user_repository.get_by_id(owner.id)
    refetched_plain = await user_repository.get_by_id(plain.id)
    assert refetched_owner is not None and refetched_owner.is_blocked is False
    assert refetched_plain is not None and refetched_plain.is_blocked is True


async def test_reconcile_matches_email_case_insensitively(
    blacklist_repository: BlacklistRepository,
    user_repository: UserRepository,
    uow,
    event_publisher,
) -> None:
    user = await user_repository.create(
        CreateUserDto(telegram_id=333, name="mixed", email="John@Example.com")
    )
    await blacklist_repository.add_entry(BlacklistKind.EMAIL, "John@Example.com")

    await reconcile_blacklist(blacklist_repository, user_repository, uow, event_publisher)

    refetched = await user_repository.get_by_id(user.id)
    assert refetched is not None and refetched.is_blocked is True


async def test_sync_skips_disabled_sources(
    blacklist_repository: BlacklistRepository, uow, monkeypatch
) -> None:
    src = await blacklist_repository.add_source(
        AddBlacklistSourceDto(url="https://feed.example/disabled.txt")
    )
    await blacklist_repository.replace_source_lists(
        src.id, ParsedSourceList(telegram_ids=[9], emails=[]), error=None
    )
    await blacklist_repository.set_source_enabled(src.id, False)

    async def never_called(url: str) -> ParsedSourceList:
        raise AssertionError(f"disabled source must not be fetched: {url}")

    monkeypatch.setattr("app.modules.blacklist.tasks.fetch_source", never_called)
    await sync_blacklist_sources(blacklist_repository, uow)

    fetched = await blacklist_repository.get_source(src.id)
    assert fetched is not None and fetched.entries_count == 1 and fetched.last_error is None


async def test_sync_replaces_lists_and_records_error(
    blacklist_repository: BlacklistRepository, uow, monkeypatch
) -> None:
    src = await blacklist_repository.add_source(
        AddBlacklistSourceDto(url="https://feed.example/list.txt")
    )

    async def fake_fetch(url: str) -> ParsedSourceList:
        return ParsedSourceList(telegram_ids=[1, 2], emails=[])

    monkeypatch.setattr("app.modules.blacklist.tasks.fetch_source", fake_fetch)
    await sync_blacklist_sources(blacklist_repository, uow)
    fetched = await blacklist_repository.get_source(src.id)
    assert fetched is not None and fetched.entries_count == 2 and fetched.last_error is None

    async def boom(url: str) -> ParsedSourceList:
        raise ValueError("dead link")

    monkeypatch.setattr("app.modules.blacklist.tasks.fetch_source", boom)
    await sync_blacklist_sources(blacklist_repository, uow)
    fetched = await blacklist_repository.get_source(src.id)
    assert fetched is not None
    assert fetched.entries_count == 2  # kept last-good
    assert fetched.last_error == "dead link"
