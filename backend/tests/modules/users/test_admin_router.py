from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import BlacklistKind, Locale, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.core.security.password import PASSWORD_MIN_LENGTH
from app.core.security.permissions import Permission
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import BlacklistRepository
from app.modules.providers import get_module_providers
from app.modules.users.api.schemas import PromoteAdminRequest
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


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncContainer:
    # Mirrors create_api_container()'s own provider list (app/core/di/container.py)
    # instead of extracting it from an already-built container -- dishka doesn't
    # expose the original Provider list back off an AsyncContainer. dishka resolves
    # providers in last-registered-wins order for a given type, so appending
    # _TestSessionProvider after the real DatabaseProvider overrides just the
    # AsyncSession factory (whose real version would open a second, independent
    # connection/transaction outside this test's session/uow fixtures) while
    # keeping every other provider (and the real UserRepository/usecase wiring)
    # untouched.
    providers = [
        *get_core_providers(),
        *get_module_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    # httpx.AsyncClient + ASGITransport runs the app in-process on the same
    # event loop as this test coroutine, unlike starlette.testclient.TestClient
    # (used in tests/api/test_app.py), which drives the ASGI app from a
    # background thread with its own anyio event loop via a blocking portal.
    # That's fine for test_app.py's DB-free routes, but here the endpoint's
    # dishka-resolved AsyncSession is the *same* asyncpg connection opened by
    # the `session` fixture on this test's loop -- asyncpg connections are
    # loop-bound, so touching them from the portal's separate loop raises
    # "Future attached to a different loop". Keeping everything on one loop
    # avoids that and keeps the request inside the same rolled-back transaction.
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _issue_token(
    user_id: int, session_repository: SessionRepository, config: AppConfig
) -> str:
    # get_current_actor requires the token's "sid" claim to reference a real,
    # non-revoked session row -- a bare create_access_token(user_id, secret)
    # call is no longer enough since the session/refresh-token rework.
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token("test-refresh-token"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    return create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())


async def _owner_token(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> tuple[UserDto, str]:
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(
                login="ownerhttp",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="ownerhttp",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    token = await _issue_token(owner.id, session_repository, config)
    return owner, token


async def test_create_admin_endpoint_returns_password_once(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.post(
        "/api/v1/admins",
        json={"login": "httpadmin", "name": "HTTP Admin"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["admin"]["login"] == "httpadmin"
    assert len(body["password"]) == PASSWORD_MIN_LENGTH
    created = await user_repository.get_by_login("httpadmin")
    assert created is not None and created.password_change_required


async def test_promote_admin_endpoint_returns_null_password_when_already_set(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    existing_hash = await hash_password("existing-password", config.crypt_key.get_secret_value())
    async with uow:
        await user_repository.create(
            CreateUserDto(
                name="Client",
                role=Role.USER,
                language=Locale.EN,
                email="promotehttp@example.com",
                password_hash=existing_hash,
            )
        )
        await uow.commit()

    response = await client.post(
        "/api/v1/admins/actions/promote",
        json={"email": "promotehttp@example.com", "login": "promotehttp-admin"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["admin"]["login"] == "promotehttp-admin"
    assert body["password"] is None


async def test_list_admins_endpoint(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.get("/api/v1/admins", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    logins = {a["login"] for a in response.json()["items"]}
    assert owner.login in logins
    owner_row = next(a for a in response.json()["items"] if a["login"] == owner.login)
    assert "ADMINS_MANAGE" in owner_row["role_permissions"]


async def test_update_own_security_settings_rejects_self_lockout(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.put(
        "/api/v1/users/me/security",
        json={"ip_allowlist": ["203.0.113.5"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    # ASGITransport's default client host is not "203.0.113.5" -- this must
    # be rejected as a self-lockout.
    assert response.status_code == 400


async def test_actor_with_ip_allowlist_is_rejected_from_other_ip(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(
                login="restrictedowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="restrictedowner",
                role=Role.OWNER,
                language=Locale.EN,
                ip_allowlist=["203.0.113.5"],
            )
        )
        await uow.commit()
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    # ASGITransport's default client host is not "203.0.113.5" -- get_current_actor
    # must reject the request.
    assert response.status_code == 401


async def test_update_admin_endpoint_omitted_field_leaves_it_unchanged(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    create_response = await client.post(
        "/api/v1/admins",
        json={
            "login": "patchadmin",
            "name": "Patch Admin",
            "permission_grants": ["OAUTH_SETTINGS_MANAGE"],
            "permission_revokes": ["BOT_SETTINGS_MANAGE"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    admin_id = create_response.json()["admin"]["id"]

    response = await client.patch(
        f"/api/v1/admins/{admin_id}",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["permission_grants"] == ["OAUTH_SETTINGS_MANAGE"]
    assert body["permission_revokes"] == ["BOT_SETTINGS_MANAGE"]


async def test_update_admin_endpoint_explicit_empty_list_clears_overrides(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    create_response = await client.post(
        "/api/v1/admins",
        json={
            "login": "patchadmin2",
            "name": "Patch Admin 2",
            "permission_grants": ["OAUTH_SETTINGS_MANAGE"],
            "permission_revokes": ["BOT_SETTINGS_MANAGE"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    admin_id = create_response.json()["admin"]["id"]

    response = await client.patch(
        f"/api/v1/admins/{admin_id}",
        json={"permission_grants": [], "permission_revokes": []},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["permission_grants"] == []
    assert body["permission_revokes"] == []


async def test_get_own_security_returns_current_allowlist(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(
                login="secgetowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="secgetowner",
                role=Role.OWNER,
                language=Locale.EN,
                ip_allowlist=["10.0.0.1"],
            )
        )
        await uow.commit()
    token = await _issue_token(owner.id, session_repository, config)

    response = await client.get(
        "/api/v1/users/me/security",
        headers={"Authorization": f"Bearer {token}", "x-forwarded-for": "10.0.0.1"},
    )

    assert response.status_code == 200
    assert response.json()["ip_allowlist"] == ["10.0.0.1"]
    assert response.json()["client_ip"] == "10.0.0.1"


async def test_get_me_includes_effective_permissions(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    permissions = response.json()["effective_permissions"]
    assert "ADMINS_MANAGE" in permissions
    assert "EVENT_LOG_VIEW" in permissions


async def test_list_users_endpoint_excludes_admins_and_owner(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner, token = await _owner_token(user_repository, session_repository, uow, config)
    async with uow:
        await user_repository.create(
            CreateUserDto(name="HTTPRegular", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    response = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    names_and_logins = {u["name"] for u in body["items"]} | {
        u["login"] for u in body["items"] if u["login"]
    }
    assert owner.login not in names_and_logins
    assert "HTTPRegular" in names_and_logins


async def test_delete_admin_endpoint_removes_admin(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    create_response = await client.post(
        "/api/v1/admins",
        json={"login": "httpdeleteadmin", "name": "HTTP Delete Admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    admin_id = create_response.json()["admin"]["id"]

    response = await client.delete(
        f"/api/v1/admins/{admin_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    deleted = await user_repository.get_by_id(admin_id)
    assert deleted is not None and deleted.deleted_at is not None


async def test_delete_admin_endpoint_rejects_owner_target(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.delete(
        f"/api/v1/admins/{owner.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409
    assert await user_repository.get_by_id(owner.id) is not None


async def test_delete_user_endpoint_removes_regular_user(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="HTTPDeleteMe", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    response = await client.delete(
        f"/api/v1/users/{target.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    deleted = await user_repository.get_by_id(target.id)
    assert deleted is not None and deleted.deleted_at is not None


async def test_delete_user_endpoint_rejects_admin_without_grant(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="plainadminhttp",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="plainadminhttp",
                role=Role.ADMIN,
                language=Locale.EN,
            )
        )
        target = await user_repository.create(
            CreateUserDto(name="HTTPNotDeleted", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()
    token = await _issue_token(admin.id, session_repository, config)

    response = await client.delete(
        f"/api/v1/users/{target.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert await user_repository.get_by_id(target.id) is not None


async def test_set_user_discount_updates_personal_discount(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="disc-target", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    response = await client.patch(
        f"/api/v1/users/{target.id}/discount",
        json={"percent": 30},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["personal_discount"] == 30


async def test_block_and_unblock_user_endpoints(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    async with uow:
        target = await user_repository.create(
            CreateUserDto(name="block-target", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()

    response = await client.post(
        f"/api/v1/users/{target.id}/actions/block", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["is_blocked"] is True

    response = await client.post(
        f"/api/v1/users/{target.id}/actions/unblock", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["is_blocked"] is False


async def test_block_user_endpoint_returns_404_for_unknown_user(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.post(
        "/api/v1/users/999999999/actions/block", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


async def test_unblock_all_endpoint_requires_unblock_all_permission(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="blockonlyadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="blockonlyadmin",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_grants=[Permission.USERS_BLOCK],
            )
        )
        await uow.commit()
    token = await _issue_token(admin.id, session_repository, config)

    response = await client.post(
        "/api/v1/users/bulk/all/unblock", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


async def test_list_users_endpoint_applies_date_and_trial_filters(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _owner, token = await _owner_token(user_repository, session_repository, uow, config)
    async with uow:
        await user_repository.create(
            CreateUserDto(name="HTTPFiltered", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()
    today = datetime.now(timezone.utc).date().isoformat()
    headers = {"Authorization": f"Bearer {token}"}

    # a bare date covers the whole day, so a user registered just now matches
    response = await client.get(
        "/api/v1/users",
        params={"created_from": today, "created_to": today, "is_trial_available": "true"},
        headers=headers,
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert [(u["name"], u["active_subscriptions"]) for u in items] == [("HTTPFiltered", 0)]

    response = await client.get(
        "/api/v1/users", params={"is_trial_available": "false"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_blacklist_matches_endpoint(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    async with uow:
        await BlacklistRepository(uow.session).add_entry(BlacklistKind.TELEGRAM_ID, "7001")
        user = await user_repository.create(
            CreateUserDto(telegram_id=7001, name="Matched", language=Locale.EN)
        )
        await uow.commit()

    response = await client.get(
        "/api/v1/users/blacklist-matches", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == body["all_total"] == 1
    # a manually added entry, not one pulled in from a list
    assert body["manual_total"] == 1
    assert body["lists_total"] == 0
    (match,) = body["items"]
    assert match["user"]["id"] == user.id
    assert match["hits"] == [
        {
            "kind": "TELEGRAM_ID",
            "value": "7001",
            "origins": [{"source_id": None, "source_name": None}],
        }
    ]


async def test_unblock_blacklist_matches_endpoint(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    async with uow:
        await BlacklistRepository(uow.session).add_entry(BlacklistKind.TELEGRAM_ID, "7002")
        user = await user_repository.create(
            CreateUserDto(telegram_id=7002, name="Matched", language=Locale.EN)
        )
        await user_repository.set_blocked(user.id, True)
        await uow.commit()

    # must not be captured by POST /users/{user_id}/actions/unblock
    response = await client.post(
        "/api/v1/users/bulk/blacklist-matches/unblock",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"unblocked": 1}


async def _create(user_repository: UserRepository, uow: UnitOfWork, **fields: object) -> UserDto:
    async with uow:
        user = await user_repository.create(CreateUserDto(language=Locale.EN, **fields))  # type: ignore[arg-type]
        await uow.commit()
    return user


async def test_get_user_returns_list_item_shape(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    customer = await _create(
        user_repository, uow, telegram_id=777001, name="customer", role=Role.USER
    )

    response = await client.get(
        f"/api/v1/users/{customer.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == customer.id
    assert response.json()["active_subscriptions"] == 0


async def test_get_user_hides_staff_without_admins_manage(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _create(
        user_repository, uow, login="hiddenowner", name="hiddenowner", role=Role.OWNER
    )
    admin = await _create(
        user_repository,
        uow,
        login="detailviewer",
        name="detailviewer",
        role=Role.ADMIN,
        permission_grants=["USERS_DETAIL_VIEW"],
    )
    token = await _issue_token(admin.id, session_repository, config)

    response = await client.get(
        f"/api/v1/users/{owner.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


async def test_users_me_is_not_shadowed_by_user_id_route(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == owner.id


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_id": 1, "email": "a@example.com"},
        {"email": "a@example.com", "telegram_username": "a"},
    ],
)
def test_promote_request_needs_exactly_one_identifier(payload: dict[str, object]) -> None:
    with pytest.raises(PydanticValidationError):
        PromoteAdminRequest.model_validate(payload)


def test_promote_request_accepts_user_id_alone() -> None:
    assert PromoteAdminRequest.model_validate({"user_id": 7}).user_id == 7
