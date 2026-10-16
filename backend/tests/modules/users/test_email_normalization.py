import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.utils.email import canonical_email, normalize_email
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ivan.Petrov+shop@Gmail.com", "ivanpetrov@gmail.com"),
        ("ivan.petrov@googlemail.com", "ivanpetrov@gmail.com"),
        ("ivan-petrov+x@ya.ru", "ivan.petrov@yandex.ru"),
        ("ivan.petrov@yandex.com", "ivan.petrov@yandex.ru"),
        ("ivan+tag@mail.ru", "ivan@mail.ru"),
        ("i.van@mail.ru", "i.van@mail.ru"),
        ("  Ann@Outlook.com ", "ann@outlook.com"),
    ],
)
def test_canonical_email(raw: str, expected: str) -> None:
    assert canonical_email(raw) == expected


def test_canonical_keeps_local_when_only_tag() -> None:
    assert canonical_email("+x@gmail.com") == "+x@gmail.com"


async def test_email_kept_as_entered_and_alias_finds_user(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    async with uow:
        created = await user_repository.create(
            CreateUserDto(name="i", email="Ivan.Petrov@Gmail.com")
        )
        found = await user_repository.get_by_email("ivanpetrov+1@googlemail.com")
    assert created.email == "ivan.petrov@gmail.com"
    assert found is not None and found.id == created.id
    canonical = await session.scalar(select(User.email_canonical).where(User.id == created.id))
    assert canonical == "ivanpetrov@gmail.com"


async def test_alias_of_taken_email_conflicts(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await user_repository.create(CreateUserDto(name="a", email="ivan.petrov@gmail.com"))
    with pytest.raises(ConflictError) as error:
        async with uow:
            await user_repository.create(CreateUserDto(name="b", email="ivanpetrov@gmail.com"))
    assert error.value.code is ErrorCode.EMAIL_TAKEN


async def test_write_target_moves_canonical(
    user_repository: UserRepository, uow: UnitOfWork, session: AsyncSession
) -> None:
    async with uow:
        user = await user_repository.create(CreateUserDto(name="m"))
    row = await session.get_one(User, user.id)
    row.email = "ivan.petrov@gmail.com"
    await session.flush()
    assert row.email_canonical == "ivanpetrov@gmail.com"
    row.email = None
    await session.flush()
    assert row.email_canonical is None
