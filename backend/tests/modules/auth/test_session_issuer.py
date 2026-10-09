import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_issue_creates_session_and_matching_access_token(
    session_repository: SessionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()

    issuer = SessionIssuer(session_repository, uow, config)
    issued = await issuer.issue(user.id, ip_address="203.0.113.1", user_agent="pytest")

    payload = decode_access_token(issued.access_token, config.jwt_secret.get_secret_value())
    assert payload["sub"] == str(user.id)

    session = await session_repository.get_active_by_id(payload["sid"])
    assert session is not None
    assert session.user_id == user.id
    assert issued.csrf_token
    assert issued.refresh_token


async def test_reissue_access_only_does_not_create_a_new_session(
    session_repository: SessionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="owner2", name="owner2", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(user.id, "203.0.113.1", "pytest")

    before = await session_repository.list_active_by_user(user.id)
    reissued = await issuer.reissue_access_only(user.id, before[0].id, "new-refresh-token")
    after = await session_repository.list_active_by_user(user.id)

    assert len(before) == len(after) == 1
    assert reissued.refresh_token == "new-refresh-token"


async def test_issue_revokes_prior_session_with_same_fingerprint(
    session_repository: SessionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="owner3", name="owner3", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    issuer = SessionIssuer(session_repository, uow, config)

    first = await issuer.issue(user.id, "203.0.113.1", "pytest-ua")
    second = await issuer.issue(user.id, "203.0.113.1", "pytest-ua")

    active = await session_repository.list_active_by_user(user.id)
    first_payload = decode_access_token(first.access_token, config.jwt_secret.get_secret_value())
    second_payload = decode_access_token(second.access_token, config.jwt_secret.get_secret_value())

    assert [session.id for session in active] == [int(second_payload["sid"])]
    assert int(first_payload["sid"]) != int(second_payload["sid"])


async def test_reissue_on_a_session_revoked_meanwhile_is_unauthorized(
    session_repository: SessionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="owner3", name="owner3", role=Role.OWNER, language=Locale.EN)
        )
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(user.id, "203.0.113.1", "pytest")
    session = (await session_repository.list_active_by_user(user.id))[0]
    async with uow:
        await session_repository.revoke_by_id(session.id)

    with pytest.raises(AuthenticationError) as error:
        await issuer.reissue_access_only(user.id, session.id, "new-refresh-token")

    assert error.value.code is ErrorCode.REFRESH_TOKEN_INVALID
