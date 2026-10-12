import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.cabinet_auth.disposable import is_disposable
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.settings.dto import UpdateCabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository

_IP = "203.0.113.1"


@pytest.mark.parametrize(
    ("email", "extra", "expected"),
    [
        ("a@mailinator.com", [], True),
        ("a@x.mailinator.com", [], True),
        ("A@MAILINATOR.com", [], True),
        ("a@gmail.com", [], False),
        ("a@notmailinator.com", [], False),
        ("a@spam.test", ["spam.test"], True),
        ("a@spam.test", [], False),
    ],
)
def test_is_disposable(email: str, extra: list[str], expected: bool) -> None:
    assert is_disposable(email, extra) is expected


async def _enable(repo: SettingsRepository, uow: UnitOfWork, **fields: object) -> None:
    async with uow:
        await repo.update_cabinet_auth_settings(UpdateCabinetAuthSettingsDto(**fields))  # type: ignore[arg-type]


async def test_new_disposable_signup_refused(
    sign_in: CabinetSignIn, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await _enable(settings_repository, uow, block_disposable_emails=True)
    with pytest.raises(ValidationError) as error:
        await sign_in.email("bot@mailinator.com", Locale.EN, InviteCodesDto(), _IP, None)
    assert error.value.code is ErrorCode.EMAIL_DISPOSABLE


async def test_extra_domain_refused(
    sign_in: CabinetSignIn, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await _enable(
        settings_repository,
        uow,
        block_disposable_emails=True,
        extra_disposable_domains=["spam.test"],
    )
    with pytest.raises(ValidationError):
        await sign_in.email("bot@spam.test", Locale.EN, InviteCodesDto(), _IP, None)


async def test_existing_user_still_signs_in(
    sign_in: CabinetSignIn,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        existing = await user_repository.create(
            CreateUserDto(name="Old", email="old@mailinator.com")
        )
    await _enable(settings_repository, uow, block_disposable_emails=True)
    user, _ = await sign_in.email("old@mailinator.com", Locale.EN, InviteCodesDto(), _IP, None)
    assert user.id == existing.id


async def test_flag_off_allows_signup(sign_in: CabinetSignIn) -> None:
    user, _ = await sign_in.email("bot@mailinator.com", Locale.EN, InviteCodesDto(), _IP, None)
    assert user.email == "bot@mailinator.com"
