import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.backups.repository import BackupRepository
from app.modules.backups.usecases import (
    CreateBackupRunUseCase,
    DeleteBackupRunUseCase,
    DownloadBackupRunUseCase,
    GetBackupRunUseCase,
    GetBackupSettingsUseCase,
    GetBackupStatsUseCase,
    ListBackupRunsUseCase,
    UpdateBackupSettingsUseCase,
)
from app.modules.backups.usecases.create_backup_run import RunBackupDispatch
from app.modules.blacklist import get_blacklist_providers
from app.modules.passkeys import get_passkey_revoker_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscription_revoker_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


class _FakeTaskDispatch:
    async def kiq(self, *, kind: str, run_id: int) -> None:
        return None


class _BackupsProvider(Provider):
    scope = Scope.REQUEST

    backup_repository = provide(BackupRepository)
    get_backup_settings_use_case = provide(GetBackupSettingsUseCase)
    get_backup_stats_use_case = provide(GetBackupStatsUseCase)
    update_backup_settings_use_case = provide(UpdateBackupSettingsUseCase)
    create_backup_run_use_case = provide(CreateBackupRunUseCase)
    list_backup_runs_use_case = provide(ListBackupRunsUseCase)
    get_backup_run_use_case = provide(GetBackupRunUseCase)
    download_backup_run_use_case = provide(DownloadBackupRunUseCase)
    delete_backup_run_use_case = provide(DeleteBackupRunUseCase)

    @provide
    def run_backup_dispatch(self) -> RunBackupDispatch:
        return _FakeTaskDispatch()  # type: ignore[return-value]


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_users_providers(),
        *get_subscription_revoker_providers(),
        *get_passkey_revoker_providers(),
        *get_auth_providers(),
        *get_api_tokens_providers(),
        *get_settings_providers(),
        *get_translations_providers(),
        *get_blacklist_providers(),
        _BackupsProvider(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _create_user(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig, role: Role, login: str
) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=login,
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    return user


async def _issue_token(
    user_id: int, session_repository: SessionRepository, config: AppConfig
) -> str:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-backups"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    # Committed, not just flushed: a request that raises rolls its own
    # transaction back, which would otherwise take this session row with it.
    await session_repository.session.commit()
    return create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())


@pytest.fixture
async def owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    # BACKUPS_* permissions are OWNER/SYSTEM-only by default (see
    # ROLE_PERMISSIONS) -- an ADMIN actor without an explicit grant gets 403,
    # same shape as tests/modules/api_tokens/test_admin_router.py.
    owner = await _create_user(user_repository, uow, config, Role.OWNER, "backupsowner")
    token = await _issue_token(owner.id, session_repository, config)
    return {"Authorization": f"Bearer {token}"}


async def test_get_settings_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/backups/settings")
    assert response.status_code == 401


async def test_owner_can_get_and_update_settings(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.get(f"{API_V1}/backups/settings", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    response = await client.put(
        f"{API_V1}/backups/settings",
        json={"enabled": True, "max_files": 3},
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert response.json()["max_files"] == 3


async def test_update_settings_rejects_zero_max_files(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.put(
        f"{API_V1}/backups/settings", json={"max_files": 0}, headers=owner_headers
    )
    assert response.status_code == 422


async def test_update_settings_rejects_zero_interval_hours(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.put(
        f"{API_V1}/backups/settings", json={"interval_hours": 0}, headers=owner_headers
    )
    assert response.status_code == 422


async def test_owner_can_trigger_and_list_runs(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_V1}/backups/runs", json={"kind": "DATABASE"}, headers=owner_headers
    )
    assert response.status_code == 202
    run_id = response.json()["id"]
    assert response.json()["status"] == "PENDING"

    response = await client.get(f"{API_V1}/backups/runs", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = await client.get(f"{API_V1}/backups/runs/{run_id}", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_second_concurrent_run_returns_409(
    client: httpx.AsyncClient,
    owner_headers: dict[str, str],
    backup_repository: BackupRepository,
    uow: UnitOfWork,
) -> None:
    first = await client.post(
        f"{API_V1}/backups/runs", json={"kind": "DATABASE"}, headers=owner_headers
    )
    assert first.status_code == 202
    async with uow:
        await backup_repository.mark_running(first.json()["id"])

    second = await client.post(
        f"{API_V1}/backups/runs", json={"kind": "DATABASE"}, headers=owner_headers
    )
    assert second.status_code == 409


async def test_download_denied_with_only_run_view_permission(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="backupsviewer",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="backupsviewer",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_grants=["BACKUPS_RUN_VIEW"],
            )
        )
        await uow.commit()
    token = await _issue_token(admin.id, session_repository, config)
    headers = {"Authorization": f"Bearer {token}"}

    # the grant passes the run-view permission check (404 = not found, not 403)...
    assert (await client.get(f"{API_V1}/backups/runs/1", headers=headers)).status_code == 404
    # ...but downloading the dump file needs BACKUPS_RUN_DOWNLOAD
    response = await client.get(f"{API_V1}/backups/runs/1/download", headers=headers)
    assert response.status_code == 403


async def test_download_returns_404_for_non_completed_run(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_V1}/backups/runs", json={"kind": "DATABASE"}, headers=owner_headers
    )
    run_id = response.json()["id"]

    response = await client.get(f"{API_V1}/backups/runs/{run_id}/download", headers=owner_headers)

    assert response.status_code == 404


async def test_owner_can_delete_run(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_V1}/backups/runs", json={"kind": "DATABASE"}, headers=owner_headers
    )
    run_id = response.json()["id"]

    response = await client.delete(f"{API_V1}/backups/runs/{run_id}", headers=owner_headers)
    assert response.status_code == 204

    response = await client.get(f"{API_V1}/backups/runs/{run_id}", headers=owner_headers)
    assert response.status_code == 404


async def test_owner_can_get_stats(
    client: httpx.AsyncClient, owner_headers: dict[str, str]
) -> None:
    await client.post(f"{API_V1}/backups/runs", json={"kind": "DATABASE"}, headers=owner_headers)
    await client.put(f"{API_V1}/backups/settings", json={"enabled": True}, headers=owner_headers)

    response = await client.get(f"{API_V1}/backups/stats", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["completed_count"] == 0  # the run is still PENDING
    assert body["last_database_backup"] is None
    assert body["next_run_at"] is not None
