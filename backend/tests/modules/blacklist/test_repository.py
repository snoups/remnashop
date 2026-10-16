from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind
from app.modules.blacklist.dto import AddBlacklistSourceDto, ParsedSourceList
from app.modules.blacklist.repository import BlacklistRepository


async def test_add_entry_normalises_and_dedupes(blacklist_repository: BlacklistRepository) -> None:
    assert await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "0123")
    # already there
    assert not await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "123")
    assert not await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "garbage")  # invalid
    bl = await blacklist_repository.get_blacklist()
    assert bl.telegram_ids == [123]


async def test_is_blacklisted_checks_manual_and_enabled_sources(
    blacklist_repository: BlacklistRepository,
) -> None:
    await blacklist_repository.add_entry(BlacklistKind.EMAIL, "Bad@Example.com")
    src = await blacklist_repository.add_source(
        AddBlacklistSourceDto(url="https://x.example/l.txt")
    )
    await blacklist_repository.replace_source_lists(
        src.id, ParsedSourceList(telegram_ids=[999], emails=[]), error=None
    )

    assert await blacklist_repository.is_blacklisted_email("bad@example.com")
    assert await blacklist_repository.is_blacklisted_telegram_id(999)
    assert not await blacklist_repository.is_blacklisted_telegram_id(111)

    await blacklist_repository.set_source_enabled(src.id, False)
    assert not await blacklist_repository.is_blacklisted_telegram_id(999)  # disabled source ignored


async def test_replace_source_lists_is_wholesale(blacklist_repository: BlacklistRepository) -> None:
    src = await blacklist_repository.add_source(
        AddBlacklistSourceDto(url="https://y.example/l.txt")
    )
    await blacklist_repository.replace_source_lists(
        src.id, ParsedSourceList(telegram_ids=[1, 2, 3], emails=["a@b.co"]), error=None
    )
    await blacklist_repository.replace_source_lists(
        src.id, ParsedSourceList(telegram_ids=[4], emails=[]), error=None
    )
    fetched = await blacklist_repository.get_source(src.id)
    assert fetched is not None and fetched.entries_count == 1
    assert not await blacklist_repository.is_blacklisted_telegram_id(1)
    assert await blacklist_repository.is_blacklisted_telegram_id(4)


async def test_all_blocked_identities_unions_manual_and_enabled(
    blacklist_repository: BlacklistRepository,
) -> None:
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "10")
    await blacklist_repository.add_entry(BlacklistKind.EMAIL, "m@n.co")
    src = await blacklist_repository.add_source(
        AddBlacklistSourceDto(url="https://z.example/l.txt")
    )
    await blacklist_repository.replace_source_lists(
        src.id, ParsedSourceList(telegram_ids=[20], emails=["s@t.co"]), error=None
    )
    ids, emails = await blacklist_repository.all_blocked_identities()
    assert ids == {10, 20}
    assert emails == {"m@n.co", "s@t.co"}


async def test_alias_of_blocked_email_is_blacklisted(
    blacklist_repository: BlacklistRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await blacklist_repository.add_entry(BlacklistKind.EMAIL, "Ivan.Petrov@gmail.com")
        assert await blacklist_repository.is_blacklisted_email("ivanpetrov+2@googlemail.com")
        assert not await blacklist_repository.is_blacklisted_email("other@gmail.com")
