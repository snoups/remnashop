import pytest

from app.core.enums import BlacklistKind, Role
from app.core.exceptions import PermissionDeniedError
from app.modules.blacklist import BlacklistRepository
from app.modules.blacklist.dto import AddBlacklistSourceDto, ParsedSourceList
from app.modules.users.blacklist_repository import UserBlacklistRepository
from app.modules.users.dto import CreateUserDto, ListBlacklistMatchesDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import ListBlacklistMatchesUseCase


async def test_lists_users_with_their_origins(
    user_repository: UserRepository, blacklist_repository: BlacklistRepository, uow
) -> None:
    await blacklist_repository.add_entry(BlacklistKind.TELEGRAM_ID, "100")
    await blacklist_repository.add_entry(BlacklistKind.EMAIL, "bad@example.com")
    await blacklist_repository.add_entry(BlacklistKind.EMAIL, "staff@example.com")
    source = await blacklist_repository.add_source(
        AddBlacklistSourceDto(url="https://s.example/l.txt", name="Feed")
    )
    await blacklist_repository.replace_source_lists(
        source.id, ParsedSourceList(telegram_ids=[100, 200], emails=[]), error=None
    )
    disabled = await blacklist_repository.add_source(
        AddBlacklistSourceDto(url="https://off.example/l.txt")
    )
    await blacklist_repository.replace_source_lists(
        disabled.id, ParsedSourceList(telegram_ids=[300], emails=[]), error=None
    )
    await blacklist_repository.set_source_enabled(disabled.id, False)

    both = await user_repository.create(
        CreateUserDto(telegram_id=100, email="Bad@Example.com", name="both")
    )
    from_source = await user_repository.create(CreateUserDto(telegram_id=200, name="src"))
    await user_repository.create(CreateUserDto(telegram_id=300, name="disabled-only"))
    await user_repository.create(CreateUserDto(telegram_id=400, name="clean"))
    await user_repository.create(
        CreateUserDto(telegram_id=500, email="staff@example.com", name="staff", role=Role.ADMIN)
    )

    owner = UserDto(id=1, telegram_id=1, name="o", role=Role.OWNER)
    use_case = ListBlacklistMatchesUseCase(
        UserBlacklistRepository(user_repository.session), blacklist_repository, uow
    )
    result = await use_case(owner, ListBlacklistMatchesDto())

    assert result.total == result.all_total == 2
    assert (result.manual_total, result.lists_total) == (1, 2)
    by_id = {match.user.id: match for match in result.items}
    assert set(by_id) == {both.id, from_source.id}

    tg_hit, email_hit = by_id[both.id].hits
    assert tg_hit.kind is BlacklistKind.TELEGRAM_ID
    assert [o.source_id for o in tg_hit.origins] == [None, source.id]
    assert email_hit.kind is BlacklistKind.EMAIL
    assert email_hit.value == "bad@example.com"
    assert [o.source_id for o in email_hit.origins] == [None]

    (hit,) = by_id[from_source.id].hits
    assert hit.origins[0].source_name == "Feed"

    manual = await use_case(owner, ListBlacklistMatchesDto(origin="manual"))
    assert [m.user.id for m in manual.items] == [both.id]
    assert manual.all_total == 2

    lists = await use_case(owner, ListBlacklistMatchesDto(origin="lists", page_size=1))
    assert lists.total == 2 and len(lists.items) == 1

    searched = await use_case(owner, ListBlacklistMatchesDto(search="src"))
    assert [m.user.id for m in searched.items] == [from_source.id]


async def test_requires_matches_permission(
    user_repository: UserRepository, blacklist_repository: BlacklistRepository, uow
) -> None:
    admin = UserDto(id=2, telegram_id=2, name="a", role=Role.ADMIN)
    with pytest.raises(PermissionDeniedError):
        await ListBlacklistMatchesUseCase(
            UserBlacklistRepository(user_repository.session), blacklist_repository, uow
        )(admin, ListBlacklistMatchesDto())
