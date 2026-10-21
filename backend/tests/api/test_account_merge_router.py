import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest.fixture
async def owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(
                login="mergehttpowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="mergehttpowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=owner.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-merge-owner"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(owner.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_preview_then_merge(
    client: httpx.AsyncClient, owner_headers: dict[str, str], user_repository: UserRepository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s", email="s@x.io"))
    target = await user_repository.create(CreateUserDto(name="t", email="t@x.io"))

    preview = await client.get(
        f"{API_V1}/users/{target.id}/merge-preview",
        params={"source_id": source.id},
        headers=owner_headers,
    )
    assert preview.status_code == 200
    keys = {c["key"] for c in preview.json()["conflicts"]}
    assert keys == {"email", "name"}
    fingerprint = preview.json()["fingerprint"]
    assert fingerprint

    merged = await client.post(
        f"{API_V1}/users/{target.id}/actions/merge",
        json={
            "source_id": source.id,
            "choices": {"email": "source", "name": "target"},
            "fingerprint": fingerprint,
        },
        headers=owner_headers,
    )
    assert merged.status_code == 200
    assert merged.json()["email"] == "s@x.io"


async def test_merge_with_missing_choice_is_400(
    client: httpx.AsyncClient, owner_headers: dict[str, str], user_repository: UserRepository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s", email="s2@x.io"))
    target = await user_repository.create(CreateUserDto(name="s", email="t2@x.io"))
    preview = await client.get(
        f"{API_V1}/users/{target.id}/merge-preview",
        params={"source_id": source.id},
        headers=owner_headers,
    )
    fingerprint = preview.json()["fingerprint"]

    response = await client.post(
        f"{API_V1}/users/{target.id}/actions/merge",
        json={"source_id": source.id, "choices": {}, "fingerprint": fingerprint},
        headers=owner_headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "MERGE_CHOICE_MISSING"


async def test_merge_with_wrong_fingerprint_is_400(
    client: httpx.AsyncClient, owner_headers: dict[str, str], user_repository: UserRepository
) -> None:
    source = await user_repository.create(CreateUserDto(name="s", email="s3@x.io"))
    target = await user_repository.create(CreateUserDto(name="t", email="t3@x.io"))

    response = await client.post(
        f"{API_V1}/users/{target.id}/actions/merge",
        json={"source_id": source.id, "choices": {}, "fingerprint": "wrong"},
        headers=owner_headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "MERGE_PREVIEW_STALE"


async def test_preview_with_missing_source_is_404(
    client: httpx.AsyncClient, owner_headers: dict[str, str], user_repository: UserRepository
) -> None:
    target = await user_repository.create(CreateUserDto(name="t"))

    response = await client.get(
        f"{API_V1}/users/{target.id}/merge-preview",
        params={"source_id": 999999},
        headers=owner_headers,
    )

    assert response.status_code == 404


async def test_merge_without_permission_is_403(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="mergehttpadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="mergehttpadmin",
                role=Role.ADMIN,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=admin.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-merge-admin"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(admin.id, session.id, config.jwt_secret.get_secret_value())
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))

    response = await client.post(
        f"{API_V1}/users/{target.id}/actions/merge",
        json={"source_id": source.id, "choices": {}, "fingerprint": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_merge_with_missing_source_is_404(
    client: httpx.AsyncClient, owner_headers: dict[str, str], user_repository: UserRepository
) -> None:
    target = await user_repository.create(CreateUserDto(name="t"))

    response = await client.post(
        f"{API_V1}/users/{target.id}/actions/merge",
        json={"source_id": 999999, "choices": {}, "fingerprint": "x"},
        headers=owner_headers,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"
