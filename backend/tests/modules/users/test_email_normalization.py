from app.core.db.uow import UnitOfWork
from app.core.utils.email import normalize_email
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


def test_normalize_email_strips_and_lowercases() -> None:
    assert normalize_email("  Ivan@Mail.RU ") == "ivan@mail.ru"


async def test_create_and_lookup_ignore_case(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        created = await user_repository.create(CreateUserDto(name="i", email="Ivan@Mail.ru"))
        found = await user_repository.get_by_email(" IVAN@mail.ru")
    assert created.email == "ivan@mail.ru"
    assert found is not None and found.id == created.id


async def test_clear_telegram_id(user_repository: UserRepository, uow: UnitOfWork) -> None:
    async with uow:
        user = await user_repository.create(CreateUserDto(name="t", telegram_id=777001))
        cleared = await user_repository.clear_telegram_id(user.id)
    assert cleared.telegram_id is None and cleared.username is None


async def test_create_blank_email_becomes_none(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        created = await user_repository.create(CreateUserDto(name="b", email="   "))
    assert created.email is None
