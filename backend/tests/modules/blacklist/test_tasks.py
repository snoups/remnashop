from app.core.enums import BlacklistKind, Role
from app.modules.blacklist import BlacklistRepository
from app.modules.blacklist.dto import AddBlacklistSourceDto, ParsedSourceList
from app.modules.blacklist.usecases import FetchBlacklistSourcesUseCase, fetch_blacklist_sources
from app.modules.users import BlockBlacklistMatchesUseCase
from app.modules.users.blacklist_repository import UserBlacklistRepository
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

    await BlockBlacklistMatchesUseCase(
        blacklist_repository, UserBlacklistRepository(user_repository.session), uow, event_publisher
    ).system()
    refetched = await user_repository.get_by_id(user.id)
    assert refetched is not None and refetched.is_blocked is True

    # entry removed -> reconcile must NOT unblock
    await blacklist_repository.remove_entry(BlacklistKind.TELEGRAM_ID, "777")
    await BlockBlacklistMatchesUseCase(
        blacklist_repository, UserBlacklistRepository(user_repository.session), uow, event_publisher
    ).system()
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

    await BlockBlacklistMatchesUseCase(
        blacklist_repository, UserBlacklistRepository(user_repository.session), uow, event_publisher
    ).system()

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

    await BlockBlacklistMatchesUseCase(
        blacklist_repository, UserBlacklistRepository(user_repository.session), uow, event_publisher
    ).system()

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

    monkeypatch.setattr(
        "app.modules.blacklist.usecases.fetch_blacklist_sources.fetch_source", never_called
    )
    await FetchBlacklistSourcesUseCase(blacklist_repository, uow).system()

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

    monkeypatch.setattr(
        "app.modules.blacklist.usecases.fetch_blacklist_sources.fetch_source", fake_fetch
    )
    await FetchBlacklistSourcesUseCase(blacklist_repository, uow).system()
    fetched = await blacklist_repository.get_source(src.id)
    assert fetched is not None and fetched.entries_count == 2 and fetched.last_error is None

    async def boom(url: str) -> ParsedSourceList:
        raise ValueError("dead link")

    monkeypatch.setattr(fetch_blacklist_sources, "fetch_source", boom)
    await FetchBlacklistSourcesUseCase(blacklist_repository, uow).system()
    fetched = await blacklist_repository.get_source(src.id)
    assert fetched is not None
    assert fetched.entries_count == 2  # kept last-good
    assert fetched.last_error == "dead link"


async def test_sync_isolates_a_source_whose_write_fails(
    blacklist_repository: BlacklistRepository, uow, monkeypatch
) -> None:
    # committed, as in production: the failing source's rollback must not take them along
    async with uow:
        bad = await blacklist_repository.add_source(
            AddBlacklistSourceDto(url="https://feed.example/a.txt")
        )
        good = await blacklist_repository.add_source(
            AddBlacklistSourceDto(url="https://feed.example/b.txt")
        )

    async def fake_fetch(url: str) -> ParsedSourceList:
        return ParsedSourceList(telegram_ids=[7], emails=[])

    replace = blacklist_repository.replace_source_lists

    async def failing_replace(source_id: int, parsed: ParsedSourceList, *, error) -> None:  # type: ignore[no-untyped-def]
        if source_id == bad.id:
            raise ValueError("value out of range")
        await replace(source_id, parsed, error=error)

    monkeypatch.setattr(fetch_blacklist_sources, "fetch_source", fake_fetch)
    monkeypatch.setattr(blacklist_repository, "replace_source_lists", failing_replace)
    await FetchBlacklistSourcesUseCase(blacklist_repository, uow).system()

    failed = await blacklist_repository.get_source(bad.id)
    synced = await blacklist_repository.get_source(good.id)
    assert failed is not None and failed.last_error == "value out of range"
    assert synced is not None and synced.entries_count == 1 and synced.last_error is None
