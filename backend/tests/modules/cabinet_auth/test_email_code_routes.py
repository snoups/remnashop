import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import API_V1, REDIS_KEY_PREFIX
from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience
from app.modules.auth.session_cookies import SESSION_COOKIES
from app.modules.cabinet_auth.email_codes import email_key
from app.modules.settings.dto import (
    UpdateAccessSettingsDto,
    UpdateCabinetAuthSettingsDto,
    UpdateEmailSettingsDto,
)
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch

_CODE_URL = f"{API_V1}/auth/email/code"
_VERIFY_URL = f"{API_V1}/auth/email/verify"


@pytest.fixture(autouse=True)
async def _email_enabled(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(email_enabled=True)
        )
        await settings_repository.update_email_settings(
            UpdateEmailSettingsDto(host="smtp.example.com", from_address="shop@example.com")
        )


def _code_of(dispatch: RecordingDispatch) -> str:
    return next(c for c in dispatch.messages[-1]["text"].split() if c.isdigit() and len(c) == 6)


async def _request_code(client: httpx.AsyncClient, dispatch: RecordingDispatch, email: str) -> str:
    response = await client.post(_CODE_URL, json={"email": email})
    assert response.status_code == 204
    return _code_of(dispatch)


async def test_request_always_204_and_second_within_a_minute_is_silent(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(name="Blocked", email="blocked@mail.ru", is_blocked=True)
        )
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(registration_enabled=False)
        )

    for email in ("blocked@mail.ru", "new@mail.ru"):
        assert (await client.post(_CODE_URL, json={"email": email})).status_code == 204
    assert len(email_dispatch.messages) == 2

    assert (await client.post(_CODE_URL, json={"email": "NEW@Mail.ru"})).status_code == 204
    assert len(email_dispatch.messages) == 2


async def test_request_when_method_disabled(
    client: httpx.AsyncClient,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(email_enabled=False)
        )
    response = await client.post(_CODE_URL, json={"email": "a@b.c"})
    assert response.status_code == 401
    assert response.json()["code"] == "CABINET_EMAIL_DISABLED"


async def test_verify_signs_in(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch
) -> None:
    code = await _request_code(client, email_dispatch, "ann@mail.ru")

    response = await client.post(_VERIFY_URL, json={"email": "ann@mail.ru", "code": code})

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert SESSION_COOKIES[SessionAudience.CABINET].refresh in response.cookies


async def test_verify_wrong_and_missing_code(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch
) -> None:
    missing = await client.post(_VERIFY_URL, json={"email": "ann@mail.ru", "code": "123456"})
    assert (missing.status_code, missing.json()["code"]) == (401, "EMAIL_CODE_EXPIRED")

    code = await _request_code(client, email_dispatch, "ann@mail.ru")
    wrong = "000000" if code != "000000" else "111111"
    response = await client.post(_VERIFY_URL, json={"email": "ann@mail.ru", "code": wrong})
    assert (response.status_code, response.json()["code"]) == (401, "EMAIL_CODE_INVALID")


async def test_verify_blocked_user(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.create(
            CreateUserDto(name="Blocked", email="blocked@mail.ru", is_blocked=True)
        )
    code = await _request_code(client, email_dispatch, "blocked@mail.ru")

    response = await client.post(_VERIFY_URL, json={"email": "blocked@mail.ru", "code": code})

    assert (response.status_code, response.json()["code"]) == (403, "USER_BLOCKED")


async def test_verify_closed_registration(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(registration_enabled=False)
        )
    code = await _request_code(client, email_dispatch, "new@mail.ru")

    response = await client.post(_VERIFY_URL, json={"email": "new@mail.ru", "code": code})

    assert (response.status_code, response.json()["code"]) == (403, "REGISTRATION_CLOSED")


async def test_exhausted_attempts_are_logged(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch, session: AsyncSession
) -> None:
    code = await _request_code(client, email_dispatch, "ann@mail.ru")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        await client.post(_VERIFY_URL, json={"email": "ann@mail.ru", "code": wrong})

    entries = list(
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "EmailCodeAttemptsExhaustedEvent"
            )
        )
    )
    assert len(entries) == 1


async def test_daily_wrong_attempt_budget_blocks_verify_and_request(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch, redis: Redis
) -> None:
    code = await _request_code(client, email_dispatch, "ann@mail.ru")
    digest = email_key("ann@mail.ru")
    await redis.set(f"{REDIS_KEY_PREFIX}cabinet:email_code_fail:{digest}", 20)

    response = await client.post(_VERIFY_URL, json={"email": "ann@mail.ru", "code": code})
    assert (response.status_code, response.json()["code"]) == (401, "EMAIL_CODE_EXPIRED")

    await redis.delete(f"{REDIS_KEY_PREFIX}cabinet:email_code_limit:min:{digest}")
    sent = len(email_dispatch.messages)
    assert (await client.post(_CODE_URL, json={"email": "ann@mail.ru"})).status_code == 204
    assert len(email_dispatch.messages) == sent


async def test_wrong_codes_count_against_the_daily_budget(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch, redis: Redis
) -> None:
    code = await _request_code(client, email_dispatch, "ann@mail.ru")
    wrong = "000000" if code != "000000" else "111111"
    await client.post(_VERIFY_URL, json={"email": "ann@mail.ru", "code": wrong})
    key = f"{REDIS_KEY_PREFIX}cabinet:email_code_fail:{email_key('ann@mail.ru')}"
    assert int(await redis.get(key)) == 1


async def test_verify_when_method_disabled(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    code = await _request_code(client, email_dispatch, "ann@mail.ru")
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(email_enabled=False)
        )
    response = await client.post(_VERIFY_URL, json={"email": "ann@mail.ru", "code": code})
    assert (response.status_code, response.json()["code"]) == (401, "CABINET_EMAIL_DISABLED")


@pytest.mark.parametrize(
    "email",
    ["a@b.c,evil@x.y", "a@b.c;x", "<a@b.c>", 'a"@b.c', "a@b.c:x", "=?utf-8?q?bad?=@gmail.com"],
)
async def test_email_with_header_steering_characters_is_rejected(
    client: httpx.AsyncClient, email: str
) -> None:
    assert (await client.post(_CODE_URL, json={"email": email})).status_code == 422
    verify = await client.post(_VERIFY_URL, json={"email": email, "code": "123456"})
    assert verify.status_code == 422


async def test_alias_shares_the_per_minute_limit(
    client: httpx.AsyncClient, email_dispatch: RecordingDispatch
) -> None:
    assert (
        await client.post(_CODE_URL, json={"email": "ivan.petrov@gmail.com"})
    ).status_code == 204
    assert (
        await client.post(_CODE_URL, json={"email": "ivanpetrov+x@gmail.com"})
    ).status_code == 204
    assert len(email_dispatch.messages) == 1


async def test_code_for_an_alias_goes_to_the_accounts_own_address(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.create(CreateUserDto(name="Victim", email="victim@mail.ru"))
    assert (await client.post(_CODE_URL, json={"email": "victim+x@mail.ru"})).status_code == 204
    [message] = email_dispatch.messages
    assert message["to"] == "victim@mail.ru"


async def test_alias_code_does_not_reach_an_owner_registered_since(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    # no account yet: the code goes to the alias itself
    code = await _request_code(client, email_dispatch, "ivan+x@mail.ru")
    assert email_dispatch.messages[-1]["to"] == "ivan+x@mail.ru"
    async with uow:
        await user_repository.create(CreateUserDto(name="Ivan", email="ivan@mail.ru"))

    response = await client.post(_VERIFY_URL, json={"email": "ivan+x@mail.ru", "code": code})

    assert (response.status_code, response.json()["code"]) == (409, "EMAIL_TAKEN")


async def test_alias_code_signs_in_its_owner(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.create(CreateUserDto(name="Ivan", email="ivan@mail.ru"))
    code = await _request_code(client, email_dispatch, "ivan+x@mail.ru")
    assert email_dispatch.messages[-1]["to"] == "ivan@mail.ru"

    response = await client.post(_VERIFY_URL, json={"email": "ivan+x@mail.ru", "code": code})

    assert response.status_code == 200
