import httpx
import pytest

from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.email_domains import is_allowed_domain
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.settings.api.schemas import UpdateCabinetAuthSettingsRequest
from app.modules.settings.dto import (
    CabinetAuthSettingsDto,
    UpdateCabinetAuthSettingsDto,
    UpdateEmailSettingsDto,
)
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch

_IP = "203.0.113.1"
_CODE_URL = f"{API_V1}/auth/email/code"


async def _configure(
    repo: SettingsRepository, uow: UnitOfWork, data: UpdateCabinetAuthSettingsDto
) -> None:
    async with uow:
        await repo.update_cabinet_auth_settings(data)


def test_defaults_restrict_to_popular_domains() -> None:
    settings = CabinetAuthSettingsDto()
    assert settings.restrict_email_domains
    assert "gmail.com" in settings.allowed_email_domains
    assert "proton.me" not in settings.allowed_email_domains


@pytest.mark.parametrize(
    ("email", "allowed"),
    [
        ("a@gmail.com", True),
        ("a@x.gmail.com", False),
        ("a@mailinator.com", False),
    ],
)
def test_allowed_domain_exact_match(email: str, allowed: bool) -> None:
    assert is_allowed_domain(email, CabinetAuthSettingsDto()) is allowed


def test_allowed_domain_ignores_case_and_spaces() -> None:
    assert is_allowed_domain("  Ivan@GMAIL.com ", CabinetAuthSettingsDto())


def test_restriction_off_allows_any() -> None:
    settings = CabinetAuthSettingsDto(restrict_email_domains=False)
    assert is_allowed_domain("bot@mailinator.com", settings)


def test_update_request_normalizes_domains() -> None:
    request = UpdateCabinetAuthSettingsRequest(
        allowed_email_domains=[" @Gmail.com", "", "mail.ru", "gmail.com"]
    )
    assert request.allowed_email_domains == ["gmail.com", "mail.ru"]


async def test_new_signup_on_other_domain_refused(sign_in: CabinetSignIn) -> None:
    with pytest.raises(ValidationError) as error:
        await sign_in.email("bot@mailinator.com", Locale.EN, InviteCodesDto(), _IP, None)
    assert error.value.code is ErrorCode.EMAIL_DOMAIN_NOT_ALLOWED


async def test_empty_allowlist_blocks_new_signups_only(
    sign_in: CabinetSignIn,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        existing = await user_repository.create(
            CreateUserDto(name="Old", email="old@mailinator.com")
        )
    await _configure(
        settings_repository, uow, UpdateCabinetAuthSettingsDto(allowed_email_domains=[])
    )
    user, _ = await sign_in.email("old@mailinator.com", Locale.EN, InviteCodesDto(), _IP, None)
    assert user.id == existing.id
    with pytest.raises(ValidationError):
        await sign_in.email("new@gmail.com", Locale.EN, InviteCodesDto(), _IP, None)


async def test_restriction_off_allows_signup(
    sign_in: CabinetSignIn, settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    await _configure(
        settings_repository, uow, UpdateCabinetAuthSettingsDto(restrict_email_domains=False)
    )
    user, _ = await sign_in.email("bot@mailinator.com", Locale.EN, InviteCodesDto(), _IP, None)
    assert user.email == "bot@mailinator.com"


@pytest.fixture
async def _email_enabled(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(email_enabled=True)
        )
        await settings_repository.update_email_settings(
            UpdateEmailSettingsDto(host="smtp.example.com", from_address="shop@example.com")
        )


@pytest.mark.usefixtures("_email_enabled")
async def test_code_not_sent_to_disallowed_new_address(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch
) -> None:
    response = await client.post(_CODE_URL, json={"email": "bot@mailinator.com"})
    assert response.status_code == 204
    assert email_dispatch.messages == []


@pytest.mark.usefixtures("_email_enabled")
async def test_code_sent_to_existing_user_on_disallowed_domain(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.create(CreateUserDto(name="Old", email="old@mailinator.com"))
    response = await client.post(_CODE_URL, json={"email": "old@mailinator.com"})
    assert response.status_code == 204
    assert len(email_dispatch.messages) == 1
