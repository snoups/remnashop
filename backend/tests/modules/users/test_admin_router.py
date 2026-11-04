from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy import update

from app.core.config import AppConfig
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Locale, RegistrationSource, Role, SessionAudience
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError as DomainValidationError
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.core.security.password import PASSWORD_MIN_LENGTH
from app.core.security.permissions import Permission
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import BlacklistRepository
from app.modules.users import unsubscribe_token
from app.modules.users.dto import CreateUserDto, RegistrationSnapshotDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import UnsubscribeMarketingUseCase
from tests.fakes.events import RecordingEventPublisher


@pytest.fixture
async def client(
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    # httpx.AsyncClient + ASGITransport runs the app on this test's loop.
    # TestClient (tests/api/test_app.py) uses a thread with its own loop, and
    # the endpoint's session is the `session` fixture's asyncpg connection,
    # which is loop-bound ("Future attached to a different loop").
    app = api_app
    app.state.dishka_container = test_container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _issue_token(
    user_id: int, session_repository: SessionRepository, config: AppConfig
) -> str:
    # get_current_actor needs the "sid" claim to point at a live session row
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{user_id}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
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
    created = await user_repository.find_by_login("httpadmin")
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
        target = await user_repository.create(
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
        json={"user_id": target.id, "login": "promotehttp-admin"},
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


async def test_list_admins_skips_overrides_of_removed_permissions(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    async with uow:
        await user_repository.create(
            CreateUserDto(
                login="staleadmin",
                name="stale",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_grants=["REMOVED_PERMISSION", Permission.USERS_VIEW.value],
                permission_revokes=["REMOVED_PERMISSION"],
            )
        )
        await uow.commit()

    response = await client.get("/api/v1/admins", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    row = next(a for a in response.json()["items"] if a["login"] == "staleadmin")
    assert row["permission_grants"] == ["USERS_VIEW"]
    assert row["permission_revokes"] == []


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

    # ASGITransport's client host isn't "203.0.113.5", so this is a self-lockout
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

    # ASGITransport's client host isn't "203.0.113.5", so get_current_actor rejects it
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
    deleted = await user_repository.find_by_id(admin_id)
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
    assert await user_repository.find_by_id(owner.id) is not None


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
    deleted = await user_repository.find_by_id(target.id)
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
    assert await user_repository.find_by_id(target.id) is not None


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
        json={"personal_discount": 30},
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
        "/api/v1/users/bulk/unblock-blacklist-matches",
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


async def test_get_user_shows_a_blocked_bot(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    customer = await _create(user_repository, uow, telegram_id=777002, name="c", role=Role.USER)
    async with uow:
        await user_repository.set_bot_blocked(customer.id, True)

    response = await client.get(
        f"/api/v1/users/{customer.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.json()["is_bot_blocked"] is True


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


_UNSUBSCRIBE_URL = "/api/v1/unsubscribe"


async def test_unsubscribe_sets_opt_out_idempotently(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig
) -> None:
    user = await _create(user_repository, uow, name="sub", email="sub@mail.ru")
    publisher = RecordingEventPublisher()
    use_case = UnsubscribeMarketingUseCase(user_repository, uow, config, publisher)
    token = unsubscribe_token(user.id, config.crypt_key.get_secret_value())

    await use_case.execute(token)
    await use_case.execute(token)

    loaded = await user_repository.find_by_id(user.id)
    assert loaded is not None and loaded.marketing_opt_out is True
    assert [(e.user.id, e.source) for e in publisher.events] == [(user.id, "link")]  # type: ignore[attr-defined]


@pytest.mark.parametrize("kind", ["garbage", "unknown", "deleted"])
async def test_unsubscribe_bad_token(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig, kind: str
) -> None:
    secret = config.crypt_key.get_secret_value()
    if kind == "garbage":
        token = "42.AAAA"
    elif kind == "unknown":
        token = unsubscribe_token(999999999, secret)
    else:
        user = await _create(user_repository, uow, name="gone", email="gone@mail.ru")
        async with uow:
            await user_repository.session.execute(
                update(User).where(User.id == user.id).values(deleted_at=datetime.now(timezone.utc))
            )
        token = unsubscribe_token(user.id, secret)

    with pytest.raises(DomainValidationError) as error:
        await UnsubscribeMarketingUseCase(
            user_repository, uow, config, RecordingEventPublisher()
        ).execute(token)
    assert error.value.code is ErrorCode.UNSUBSCRIBE_TOKEN_INVALID


async def test_unsubscribe_route(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user = await _create(user_repository, uow, name="one-click", email="oc@mail.ru")
    token = unsubscribe_token(user.id, config.crypt_key.get_secret_value())

    response = await client.post(
        f"{_UNSUBSCRIBE_URL}?token={token}",
        content="List-Unsubscribe=One-Click",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 204
    loaded = await user_repository.find_by_id(user.id)
    assert loaded is not None and loaded.marketing_opt_out is True

    bad = await client.post(f"{_UNSUBSCRIBE_URL}?token=1.AAAA")
    assert bad.status_code == 400
    assert bad.json()["code"] == ErrorCode.UNSUBSCRIBE_TOKEN_INVALID.name

    assert (await client.get(f"{_UNSUBSCRIBE_URL}?token={token}")).status_code == 405


async def test_clear_undeliverable(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    target = await _create(user_repository, uow, name="bounced", email="bounced@mail.ru")
    async with uow:
        await user_repository.set_email_undeliverable(target.id, datetime.now(timezone.utc))
    url = f"/api/v1/users/{target.id}/actions/clear-email-undeliverable"

    response = await client.post(url, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email_undeliverable_at"] is None
    loaded = await user_repository.find_by_id(target.id)
    assert loaded is not None and loaded.email_undeliverable_at is None

    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="norevoke",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="norevoke",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_revokes=[Permission.USERS_EMAIL_UNDELIVERABLE_CLEAR.value],
            )
        )
    admin_token = await _issue_token(admin.id, session_repository, config)
    denied = await client.post(url, headers={"Authorization": f"Bearer {admin_token}"})
    assert denied.status_code == 403


async def test_registration_snapshot_is_shown_with_its_browser(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)
    old = await _create(user_repository, uow, telegram_id=777011, name="old", role=Role.USER)
    fresh = await _create(user_repository, uow, telegram_id=777012, name="new", role=Role.USER)
    async with uow:
        await user_repository.add_registration(
            fresh.id,
            RegistrationSnapshotDto(
                source=RegistrationSource.CABINET_EMAIL,
                ip_address="203.0.113.9",
                user_agent="Mozilla/5.0 (Macintosh) Chrome/130.0 Safari/537.36",
            ),
        )
    headers = {"Authorization": f"Bearer {token}"}

    none = await client.get(f"/api/v1/users/{old.id}/registration", headers=headers)
    shown = await client.get(f"/api/v1/users/{fresh.id}/registration", headers=headers)

    assert none.json() == {"registration": None}
    body = shown.json()["registration"]
    assert body["source"] == "CABINET_EMAIL"
    assert body["ip_address"] == "203.0.113.9"
    assert body["browser"] == "Chrome on macOS"
