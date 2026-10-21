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
from app.core.security.permissions import (
    PERMISSION_METADATA,
    ROLE_PERMISSIONS,
    TOKEN_GRANTABLE_PERMISSIONS,
    Permission,
)
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


async def _owner_token(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> str:
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(
                login="catalogowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="catalogowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=owner.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    return create_access_token(owner.id, session.id, config.jwt_secret.get_secret_value())


async def test_permissions_catalog_returns_every_metadata_entry(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/permissions/catalog", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    entries = response.json()["items"]
    assert len(entries) == len(PERMISSION_METADATA)

    by_permission = {entry["permission"]: entry for entry in entries}
    for permission, meta in PERMISSION_METADATA.items():
        assert by_permission[permission.value]["resource"] == meta.resource
        assert by_permission[permission.value]["kind"] == meta.kind
        assert by_permission[permission.value]["token_grantable"] == (
            permission in TOKEN_GRANTABLE_PERMISSIONS
        )


def test_dialogs_permissions_registered() -> None:
    for perm in (
        Permission.DIALOGS_WINDOWS_VIEW,
        Permission.DIALOGS_CATALOG_VIEW,
        Permission.DIALOGS_WINDOWS_UPDATE,
        Permission.DIALOGS_WINDOWS_BUTTONS_UPDATE,
        Permission.DIALOGS_WINDOWS_CREATE,
        Permission.DIALOGS_WINDOWS_DELETE,
        Permission.DIALOGS_WINDOWS_RESET,
        Permission.DIALOGS_WINDOWS_RESET_ALL,
    ):
        assert perm in PERMISSION_METADATA
        assert PERMISSION_METADATA[perm].resource == "dialogs"
        assert perm in ROLE_PERMISSIONS[Role.ADMIN]
    assert PERMISSION_METADATA[Permission.DIALOGS_WINDOWS_VIEW].kind == "read"
    assert PERMISSION_METADATA[Permission.DIALOGS_WINDOWS_UPDATE].kind == "write"
