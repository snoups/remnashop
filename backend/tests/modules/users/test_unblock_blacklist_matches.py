from app.core.enums import BlacklistKind, Role
from app.modules.blacklist import BlacklistRepository
from app.modules.blacklist.dto import AddBlacklistSourceDto, ParsedSourceList
from app.modules.users.blacklist_repository import UserBlacklistRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import UnblockBlacklistMatchesUseCase


async def test_unblocks_matches_and_drops_their_manual_entries(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow,
    event_publisher,
) -> None:
    # the outbox row has a real FK to users.id
    owner = await user_repository.create(CreateUserDto(login="owner", name="o", role=Role.OWNER))
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "100")
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "999")
    await blacklist_repository.add_entry(BlacklistKind.EMAIL, "bad@example.com")
    source = await blacklist_repository.add_source(AddBlacklistSourceDto(url="https://s.example/l"))
    await blacklist_repository.replace_source_lists(
        source.id, ParsedSourceList(telegram_ids=[200], emails=[]), error=None
    )

    manual = await user_repository.create(
        CreateUserDto(telegram_id=100, email="Bad@Example.com", name="m")
    )
    listed = await user_repository.create(CreateUserDto(telegram_id=200, name="l"))
    other = await user_repository.create(CreateUserDto(telegram_id=300, name="o"))
    for user in (manual, listed, other):
        await user_repository.set_blocked(user.id, True)

    use_case = UnblockBlacklistMatchesUseCase(
        UserBlacklistRepository(user_repository.session), blacklist_repository, uow, event_publisher
    )
    assert await use_case(owner) == 2

    for user, blocked in ((manual, False), (listed, False), (other, True)):
        fetched = await user_repository.find_by_id(user.id)
        assert fetched is not None and fetched.is_blocked is blocked
    blacklist = await blacklist_repository.get_blacklist()
    # unregistered manual entries stay; source entries are untouched
    assert blacklist.telegram_ids == [999]
    assert blacklist.emails == []
    assert await blacklist_repository.is_blacklisted_telegram_id(200)
