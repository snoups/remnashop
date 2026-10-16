import httpx
import pytest

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.modules.auth.repository import SessionRepository
from app.modules.settings.dto import UpdateCabinetAuthSettingsDto, UpdateEmailSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.identity_links.conftest import bearer

LINK_CODE = f"{API_V1}/users/me/identities/email/code"
LINK_VERIFY = f"{API_V1}/users/me/identities/email/verify"
LOGIN_CODE = f"{API_V1}/auth/email/code"
LOGIN_VERIFY = f"{API_V1}/auth/email/verify"


@pytest.fixture
async def email_enabled(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(email_enabled=True)
        )
        await settings_repository.update_email_settings(
            UpdateEmailSettingsDto(host="smtp.example.com", from_address="shop@example.com")
        )


def _code_of(dispatch: RecordingDispatch) -> str:
    return next(c for c in dispatch.messages[-1]["text"].split() if c.isdigit() and len(c) == 6)


@pytest.fixture
async def headers(
    user_repository: UserRepository, session_repository: SessionRepository, config: AppConfig
) -> dict[str, str]:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=7001))
    return await bearer(user.id, session_repository, config)


@pytest.mark.usefixtures("email_enabled")
async def test_link_email_by_code(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch, headers: dict[str, str]
) -> None:
    assert (
        await client.post(LINK_CODE, json={"email": "new@gmail.com"}, headers=headers)
    ).status_code == 204
    response = await client.post(
        LINK_VERIFY,
        json={"email": "new@gmail.com", "code": _code_of(email_dispatch)},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "linked"


@pytest.mark.usefixtures("email_enabled")
async def test_login_code_not_accepted_for_link(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch, headers: dict[str, str]
) -> None:
    await client.post(LOGIN_CODE, json={"email": "new@gmail.com"})
    response = await client.post(
        LINK_VERIFY,
        json={"email": "new@gmail.com", "code": _code_of(email_dispatch)},
        headers=headers,
    )
    assert response.status_code == 401
    assert response.json()["code"] == "EMAIL_CODE_EXPIRED"


@pytest.mark.usefixtures("email_enabled")
async def test_link_code_not_accepted_for_login(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch, headers: dict[str, str]
) -> None:
    await client.post(LINK_CODE, json={"email": "new@gmail.com"}, headers=headers)
    response = await client.post(
        LOGIN_VERIFY, json={"email": "new@gmail.com", "code": _code_of(email_dispatch)}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "EMAIL_CODE_EXPIRED"


@pytest.mark.usefixtures("email_enabled")
async def test_wrong_code(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch, headers: dict[str, str]
) -> None:
    await client.post(LINK_CODE, json={"email": "new@gmail.com"}, headers=headers)
    wrong = "000000" if _code_of(email_dispatch) != "000000" else "111111"
    response = await client.post(
        LINK_VERIFY, json={"email": "new@gmail.com", "code": wrong}, headers=headers
    )
    assert response.status_code == 401
    assert response.json()["code"] == "EMAIL_CODE_INVALID"


async def test_email_disabled(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(LINK_CODE, json={"email": "new@gmail.com"}, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "CABINET_EMAIL_DISABLED"
