import time
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.public import get_auth_context
from app.core.actor import Actor, SyntheticActor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def _actor_of(*args: Any) -> Actor:
    return (await get_auth_context.__dishka_orig_func__(*args)).actor


def _fake_request() -> Request:
    scope = {"type": "http", "client": ("203.0.113.1", 12345), "headers": []}
    return Request(scope)


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _create_user_and_session(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
) -> tuple[int, int]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("token"),
            ip_address="203.0.113.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    return user.id, session.id


async def test_accepts_valid_token_with_active_session(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user_id, session_id = await _create_user_and_session(user_repository, session_repository, uow)
    token = create_access_token(user_id, session_id, config.jwt_secret.get_secret_value())

    actor = await _actor_of(
        _fake_request(),
        config,
        user_repository,
        session_repository,
        api_token_repository,
        uow,
        _credentials(token),
    )

    assert actor.id == user_id


async def test_rejects_token_with_revoked_session(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user_id, session_id = await _create_user_and_session(user_repository, session_repository, uow)
    await session_repository.revoke_by_id(session_id)
    token = create_access_token(user_id, session_id, config.jwt_secret.get_secret_value())

    with pytest.raises(HTTPException) as exc_info:
        await _actor_of(
            _fake_request(),
            config,
            user_repository,
            session_repository,
            api_token_repository,
            uow,
            _credentials(token),
        )
    assert exc_info.value.status_code == 401


async def test_rejects_token_with_unknown_sid(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user_id, _ = await _create_user_and_session(user_repository, session_repository, uow)
    token = create_access_token(user_id, 999_999, config.jwt_secret.get_secret_value())

    with pytest.raises(HTTPException) as exc_info:
        await _actor_of(
            _fake_request(),
            config,
            user_repository,
            session_repository,
            api_token_repository,
            uow,
            _credentials(token),
        )
    assert exc_info.value.status_code == 401


async def test_rejects_pre_migration_token_missing_sid(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user_id, _ = await _create_user_and_session(user_repository, session_repository, uow)
    old_style_token = pyjwt.encode(
        {"sub": str(user_id), "exp": int(time.time()) + 900},
        config.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc_info:
        await _actor_of(
            _fake_request(),
            config,
            user_repository,
            session_repository,
            api_token_repository,
            uow,
            _credentials(old_style_token),
        )
    assert exc_info.value.status_code == 401


async def test_accepts_valid_api_token(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    secret = "a-plaintext-token-secret"
    async with uow:
        await api_token_repository.create(
            CreateApiTokenDto(
                name="ci-script",
                scopes=[Permission.BANNERS_UPLOAD.value],
                token_hash=hash_refresh_token(secret),
                created_by_user_id=None,
                expires_at=None,
            )
        )
        await uow.commit()

    actor = await _actor_of(
        _fake_request(),
        config,
        user_repository,
        session_repository,
        api_token_repository,
        uow,
        _credentials(secret),
    )

    assert actor.id == 0
    assert isinstance(actor, SyntheticActor)
    assert actor.is_privileged
    assert actor.permission_grants == [Permission.BANNERS_UPLOAD.value]


async def test_rejects_revoked_api_token(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    secret = "another-plaintext-secret"
    async with uow:
        token = await api_token_repository.create(
            CreateApiTokenDto(
                name="ci-script",
                scopes=[Permission.BANNERS_UPLOAD.value],
                token_hash=hash_refresh_token(secret),
                created_by_user_id=None,
                expires_at=None,
            )
        )
        await uow.commit()
    await api_token_repository.revoke_by_id(token.id)

    with pytest.raises(HTTPException) as exc_info:
        await _actor_of(
            _fake_request(),
            config,
            user_repository,
            session_repository,
            api_token_repository,
            uow,
            _credentials(secret),
        )
    assert exc_info.value.status_code == 401


async def test_rejects_unknown_bearer_credential(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _actor_of(
            _fake_request(),
            config,
            user_repository,
            session_repository,
            api_token_repository,
            uow,
            _credentials("not-a-jwt-and-not-a-known-token"),
        )
    assert exc_info.value.status_code == 401


async def test_require_admin_user_refuses_api_token(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    secret = "another-token-secret-for-security-route"
    async with uow:
        await api_token_repository.create(
            CreateApiTokenDto(
                name="ci-script",
                scopes=[Permission.BANNERS_UPLOAD.value],
                token_hash=hash_refresh_token(secret),
                created_by_user_id=None,
                expires_at=None,
            )
        )
        await uow.commit()

    actor = await _actor_of(
        _fake_request(),
        config,
        user_repository,
        session_repository,
        api_token_repository,
        uow,
        _credentials(secret),
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_admin_user(actor)

    assert exc_info.value.status_code == 403


def _request_from(ip: str) -> Request:
    return Request({"type": "http", "client": (ip, 12345), "headers": []})


@pytest.mark.parametrize(
    ("allowlist", "ip", "allowed"),
    [
        (["10.0.0.0/8"], "203.0.113.5", False),
        (["10.0.0.0/8"], "10.1.2.3", True),
        ([], "203.0.113.5", True),
    ],
)
async def test_api_token_ip_allowlist(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
    config: AppConfig,
    allowlist: list[str],
    ip: str,
    allowed: bool,
) -> None:
    secret = f"ip-secret-{ip}-{len(allowlist)}"
    async with uow:
        await api_token_repository.create(
            CreateApiTokenDto(
                name="ci-script",
                scopes=[Permission.BANNERS_UPLOAD.value],
                token_hash=hash_refresh_token(secret),
                created_by_user_id=None,
                expires_at=None,
                ip_allowlist=allowlist,
            )
        )
        await uow.commit()

    call = _actor_of(
        _request_from(ip),
        config,
        user_repository,
        session_repository,
        api_token_repository,
        uow,
        _credentials(secret),
    )
    if allowed:
        assert (await call).id == 0
    else:
        with pytest.raises(HTTPException) as exc_info:
            await call
        assert exc_info.value.status_code == 401
        assert exc_info.value.code == "IP_NOT_ALLOWED"  # type: ignore[attr-defined]
