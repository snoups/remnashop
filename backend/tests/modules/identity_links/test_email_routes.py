import httpx
import pytest
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import API_V1, REDIS_KEY_PREFIX
from app.core.db.uow import UnitOfWork
from app.modules.auth.repository import SessionRepository
from app.modules.cabinet_auth import email_key
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
    assert email_dispatch.messages[0]["subject"].startswith("Your linking code:")


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
    assert response.status_code == 400
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
    assert response.status_code == 400
    assert response.json()["code"] == "EMAIL_CODE_INVALID"


async def test_email_disabled(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(LINK_CODE, json={"email": "new@gmail.com"}, headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "CABINET_EMAIL_DISABLED"


@pytest.mark.usefixtures("email_enabled")
async def test_link_code_for_an_owned_alias_goes_to_the_owner_mailbox(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    headers: dict[str, str],
    user_repository: UserRepository,
) -> None:
    # john+x and john are different mailboxes on hosts where "+" is part of the name
    await user_repository.create(CreateUserDto(name="victim", email="john+x@example.org"))

    await client.post(LINK_CODE, json={"email": "john@example.org"}, headers=headers)

    assert email_dispatch.messages[-1]["to"] == "john+x@example.org"


@pytest.mark.usefixtures("email_enabled")
async def test_no_link_code_for_a_new_address_that_could_never_be_attached(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch, headers: dict[str, str]
) -> None:
    # example.org is outside the default domain allowlist and owned by nobody
    response = await client.post(LINK_CODE, json={"email": "new@example.org"}, headers=headers)

    assert response.status_code == 204
    assert email_dispatch.messages == []


@pytest.mark.usefixtures("email_enabled")
async def test_no_link_code_while_another_email_is_linked(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    user = await user_repository.create(
        CreateUserDto(name="has-email", telegram_id=7002, email="mine@gmail.com")
    )
    own = await bearer(user.id, session_repository, config)

    response = await client.post(LINK_CODE, json={"email": "other@gmail.com"}, headers=own)

    assert response.status_code == 409
    assert email_dispatch.messages == []


@pytest.mark.usefixtures("email_enabled")
async def test_failed_links_leave_the_mailbox_sign_in_budget_alone(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    headers: dict[str, str],
    redis: Redis,
) -> None:
    await client.post(LINK_CODE, json={"email": "victim@gmail.com"}, headers=headers)
    wrong = "000000" if _code_of(email_dispatch) != "000000" else "111111"
    await client.post(
        LINK_VERIFY, json={"email": "victim@gmail.com", "code": wrong}, headers=headers
    )

    sign_in_budget = f"{REDIS_KEY_PREFIX}cabinet:email_code_fail:{email_key('victim@gmail.com')}"
    assert await redis.get(sign_in_budget) is None


@pytest.mark.usefixtures("email_enabled")
async def test_alias_link_code_does_not_reach_an_owner_registered_since(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    headers: dict[str, str],
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    await client.post(LINK_CODE, json={"email": "ivan+x@mail.ru"}, headers=headers)
    assert email_dispatch.messages[-1]["to"] == "ivan+x@mail.ru"
    async with uow:
        await user_repository.create(CreateUserDto(name="Ivan", email="ivan@mail.ru"))

    response = await client.post(
        LINK_VERIFY,
        json={"email": "ivan+x@mail.ru", "code": _code_of(email_dispatch)},
        headers=headers,
    )

    assert (response.status_code, response.json()["code"]) == (409, "EMAIL_TAKEN")
