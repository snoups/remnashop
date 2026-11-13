import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.models import Subscription
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider, Role
from app.modules.auth.repository import SessionRepository
from app.modules.identity_links.dto import IdentityClaimDto, IdentityKind
from app.modules.identity_links.linker import IdentityLinker
from app.modules.oauth import CreateOAuthIdentityDto
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.settings.dto import UpdateCabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.broadcasts.factories import add_subscription
from tests.modules.identity_links.conftest import bearer

IDENTITIES = f"{API_V1}/users/me/identities"
MERGE = f"{API_V1}/users/me/merge"


async def _merge_token(
    linker: IdentityLinker, user_repository: UserRepository, session: AsyncSession
) -> tuple[UserDto, UserDto, str]:
    current = await user_repository.create(CreateUserDto(name="current", telegram_id=6100))
    other = await user_repository.create(CreateUserDto(name="other", email="other@gmail.com"))
    await add_subscription(session, other.id)
    result = await linker.link(
        current, IdentityClaimDto(kind=IdentityKind.EMAIL, email="other@gmail.com"), "127.0.0.1"
    )
    assert result.status == "merge_required" and result.merge_token
    return current, other, result.merge_token


async def _subscriptions(session: AsyncSession, user_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Subscription).where(Subscription.user_id == user_id)
        )
        or 0
    )


async def test_list_identities(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=6001, username="name"))
    headers = await bearer(user.id, session_repository, config)

    response = await client.get(IDENTITIES, headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"kind": "TELEGRAM", "linked": True, "label": "@name", "editable": True},
            {"kind": "EMAIL", "linked": False, "label": None, "editable": True},
        ],
        "total": 2,
    }

    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(google_enabled=True)
        )
    items = (await client.get(IDENTITIES, headers=headers)).json()["items"]
    assert {"kind": "GOOGLE", "linked": False, "label": None, "editable": True} in items
    assert all(item["kind"] != "YANDEX" for item in items)


async def test_linked_provider_listed_while_disabled(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    config: AppConfig,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=6002))
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.YANDEX, external_id="y-9", external_login=None
        )
    )
    headers = await bearer(user.id, session_repository, config)

    items = (await client.get(IDENTITIES, headers=headers)).json()["items"]

    assert {"kind": "YANDEX", "linked": True, "label": "y-9", "editable": True} in items


async def test_unlink_last_method_conflict(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=6003))
    headers = await bearer(user.id, session_repository, config)

    response = await client.delete(f"{IDENTITIES}/telegram", headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "LAST_SIGN_IN_METHOD"


async def test_unlink_telegram_keeps_email(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    user = await user_repository.create(
        CreateUserDto(name="me", telegram_id=6004, email="me@gmail.com")
    )
    headers = await bearer(user.id, session_repository, config)

    response = await client.delete(f"{IDENTITIES}/telegram", headers=headers)

    assert response.status_code == 204
    fresh = await user_repository.find_by_id(user.id)
    assert fresh is not None and fresh.telegram_id is None and fresh.email == "me@gmail.com"


async def test_unlink_email_with_only_non_cabinet_identity_conflict(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    config: AppConfig,
) -> None:
    # GITHUB can't sign into the cabinet, so it must not count as a remaining method
    user = await user_repository.create(CreateUserDto(name="me", email="me@gmail.com"))
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="gh-1", external_login=None
        )
    )
    headers = await bearer(user.id, session_repository, config)

    response = await client.delete(f"{IDENTITIES}/email", headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "LAST_SIGN_IN_METHOD"


async def test_unlink_oauth_and_unlinked_kind(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    config: AppConfig,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=6005))
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GOOGLE, external_id="g-9", external_login=None
        )
    )
    headers = await bearer(user.id, session_repository, config)

    assert (await client.delete(f"{IDENTITIES}/email", headers=headers)).status_code == 204
    assert (await client.delete(f"{IDENTITIES}/google", headers=headers)).status_code == 204
    assert await oauth_identity_repository.list_by_user(user.id) == []
    assert (await client.delete(f"{IDENTITIES}/github", headers=headers)).status_code == 422


async def test_merge_confirms_token(
    client: httpx.AsyncClient,
    linker: IdentityLinker,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    session: AsyncSession,
    config: AppConfig,
) -> None:
    current, other, token = await _merge_token(linker, user_repository, session)
    headers = await bearer(current.id, session_repository, config)

    response = await client.post(MERGE, json={"merge_token": token}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == current.id and body["email"] == "other@gmail.com"
    assert "effective_permissions" in body
    assert await _subscriptions(session, current.id) == 1
    assert await _subscriptions(session, other.id) == 0

    again = await client.post(MERGE, json={"merge_token": token}, headers=headers)
    assert again.status_code == 409
    assert again.json()["code"] == "MERGE_TOKEN_INVALID"


async def test_merge_token_of_other_user(
    client: httpx.AsyncClient,
    linker: IdentityLinker,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    session: AsyncSession,
    config: AppConfig,
) -> None:
    _, other, token = await _merge_token(linker, user_repository, session)
    stranger = await user_repository.create(CreateUserDto(name="stranger", telegram_id=6101))
    headers = await bearer(stranger.id, session_repository, config)

    response = await client.post(MERGE, json={"merge_token": token}, headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "MERGE_TOKEN_INVALID"
    assert await _subscriptions(session, other.id) == 1


async def test_merge_after_identity_moved(
    client: httpx.AsyncClient,
    linker: IdentityLinker,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    session: AsyncSession,
    config: AppConfig,
) -> None:
    current, other, token = await _merge_token(linker, user_repository, session)
    # the other account unlinked the address after the token was issued
    await user_repository.set_email(other.id, None)
    headers = await bearer(current.id, session_repository, config)

    response = await client.post(MERGE, json={"merge_token": token}, headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "MERGE_TOKEN_INVALID"
    gone = await user_repository.find_by_id(other.id)
    assert gone is not None and gone.deleted_at is None
    assert await _subscriptions(session, other.id) == 1


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("DELETE", f"{IDENTITIES}/email", None),
        ("DELETE", f"{IDENTITIES}/telegram", None),
        ("POST", MERGE, {"merge_token": "x"}),
        ("POST", f"{IDENTITIES}/email/code", {"email": "a@gmail.com"}),
        ("POST", f"{IDENTITIES}/email/verify", {"email": "a@gmail.com", "code": "123456"}),
        ("POST", f"{IDENTITIES}/telegram/deeplink", None),
        ("POST", f"{IDENTITIES}/telegram/signin", {"token": "x"}),
        ("POST", f"{IDENTITIES}/oauth/telegram/authorize", None),
    ],
)
async def test_staff_cabinet_session_forbidden_outside_cabinet_only_providers(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
    method: str,
    url: str,
    body: object,
) -> None:
    staff = await user_repository.create(
        CreateUserDto(name="boss", login="boss", role=Role.ADMIN, telegram_id=6200)
    )
    headers = await bearer(staff.id, session_repository, config)

    response = await client.request(method, url, json=body, headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_blocked_customer_forbidden(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    user = await user_repository.create(CreateUserDto(name="me", telegram_id=6300, is_blocked=True))
    headers = await bearer(user.id, session_repository, config)

    response = await client.get(IDENTITIES, headers=headers)

    # get_current_actor refuses a blocked account before any route dependency
    assert response.status_code == 401
    assert response.json()["code"] == "USER_BLOCKED"


async def test_without_session(client: httpx.AsyncClient) -> None:
    assert (await client.get(IDENTITIES)).status_code == 401
    assert (await client.delete(f"{IDENTITIES}/email")).status_code == 401
    assert (await client.post(MERGE, json={"merge_token": "x"})).status_code == 401


async def test_staff_lists_identities_with_only_cabinet_providers_editable(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(google_enabled=True)
        )
    staff = await user_repository.create(
        CreateUserDto(name="boss", login="boss", role=Role.ADMIN, telegram_id=6201)
    )
    headers = await bearer(staff.id, session_repository, config)

    response = await client.get(IDENTITIES, headers=headers)

    assert response.status_code == 200
    editable = {item["kind"]: item["editable"] for item in response.json()["items"]}
    assert editable == {"TELEGRAM": False, "EMAIL": False, "GOOGLE": True}


async def test_staff_unlinks_a_cabinet_only_provider(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    oauth_identity_repository: OAuthIdentityRepository,
    config: AppConfig,
) -> None:
    staff = await user_repository.create(
        CreateUserDto(name="boss", login="boss", role=Role.ADMIN, telegram_id=6202)
    )
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=staff.id,
            provider=OAuthProvider.YANDEX,
            external_id="y-staff",
            external_login=None,
        )
    )
    headers = await bearer(staff.id, session_repository, config)

    response = await client.delete(f"{IDENTITIES}/yandex", headers=headers)

    assert response.status_code == 204
    assert await oauth_identity_repository.list_by_user(staff.id) == []
