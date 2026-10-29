import datetime
from datetime import timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.plans.usecases import get_plan_share_urls
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
async def client(
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    app = api_app
    app.state.dishka_container = test_container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _token_for(
    role: Role,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> str:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=f"planstest{role.value}",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=f"planstest{role.value}",
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{role.value}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    return create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())


async def test_list_plans_requires_admin_role(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.USER, user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/plans", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


async def test_list_plans_rejects_unauthenticated_request(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/plans")

    assert response.status_code == 401


async def test_owner_can_create_and_list_plan(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        f"{API_V1}/plans",
        headers=headers,
        json={
            "public_code": "basic",
            "name": "Basic",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
        },
    )
    assert create_response.status_code == 201

    list_response = await client.get(f"{API_V1}/plans", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1


async def test_catalog_excludes_inactive_plan_for_regular_user(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner_token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    await client.post(
        f"{API_V1}/plans",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "public_code": "basic",
            "name": "Basic",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
        },
    )

    user_token = await _token_for(Role.USER, user_repository, session_repository, uow, config)
    catalog_response = await client.get(
        f"{API_V1}/plans/catalog", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert catalog_response.status_code == 200
    assert catalog_response.json()["items"] == []


async def test_catalog_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/plans/catalog")

    assert response.status_code == 401


async def test_plan_tag_takes_only_what_the_panel_accepts(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    plan = {"name": "Basic", "type": "BOTH", "traffic_limit": 100, "device_limit": 3}

    response = await client.post(
        f"{API_V1}/plans",
        headers={"Authorization": f"Bearer {token}"},
        json={**plan, "tag": "Popular"},
    )

    assert response.status_code == 422


async def test_a_null_clears_a_plan_text_and_a_missing_field_keeps_it(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        f"{API_V1}/plans",
        headers=headers,
        json={
            "name": "Basic",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
            "tag": "VIP",
            "badge": "POPULAR",
        },
    )

    response = await client.patch(
        f"{API_V1}/plans/{created.json()['id']}", headers=headers, json={"badge": None}
    )

    assert (response.json()["badge"], response.json()["tag"]) == (None, "VIP")


async def test_catalog_excludes_pii_and_infra_fields_for_active_plan(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner_token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    create_response = await client.post(
        f"{API_V1}/plans",
        headers=owner_headers,
        json={
            "public_code": "basic",
            "name": "Basic",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
            "tag": "VIP_USERS",
            "badge": "BEST_VALUE",
        },
    )
    plan_id = create_response.json()["id"]
    await client.put(
        f"{API_V1}/plans/{plan_id}/durations",
        headers=owner_headers,
        json={"durations": [{"days": 30, "order_index": 0, "base_price": "9.99"}]},
    )
    await client.put(
        f"{API_V1}/plans/{plan_id}/squads",
        headers=owner_headers,
        json={"internal_squads": ["11111111-1111-1111-1111-111111111111"], "external_squad": None},
    )
    await client.patch(
        f"{API_V1}/plans/{plan_id}",
        headers=owner_headers,
        json={"is_active": True},
    )

    user_token = await _token_for(Role.USER, user_repository, session_repository, uow, config)
    catalog_response = await client.get(
        f"{API_V1}/plans/catalog", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert catalog_response.status_code == 200
    assert catalog_response.json()["anchor_currency"] == "USD"
    plan = catalog_response.json()["items"][0]
    assert "public_code" not in plan
    assert "allowed_emails" not in plan
    assert "allowed_telegram_ids" not in plan
    assert "internal_squads" not in plan
    assert "tag" not in plan
    assert plan["badge"] == "BEST_VALUE"

    code = create_response.json()["public_code"]
    by_code = await client.get(
        f"{API_V1}/plans/catalog",
        params={"plan_code": code},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    wrong = await client.get(
        f"{API_V1}/plans/catalog",
        params={"plan_code": code + "x"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert [p["id"] for p in by_code.json()["items"]] == [plan_id]
    assert wrong.json()["items"] == []
    assert "external_squad" not in plan
    assert "availability" not in plan
    assert "is_active" not in plan


async def test_catalog_refuses_an_api_token(
    client: httpx.AsyncClient, session: AsyncSession, uow: UnitOfWork
) -> None:
    # the catalog is filtered by the caller's own purchase history and referrer,
    # which a staff token doesn't have
    secret = "test-api-token-secret"
    async with uow:
        await ApiTokenRepository(session).create(
            CreateApiTokenDto(
                name="script",
                token_hash=hash_refresh_token(secret),
                scopes=[Permission.PLANS_VIEW.value],
                created_by_user_id=None,
                expires_at=None,
            )
        )

    response = await client.get(
        f"{API_V1}/plans/catalog", headers={"Authorization": f"Bearer {secret}"}
    )

    assert response.status_code == 403


async def test_plan_switches_default_on_and_can_be_turned_off(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        f"{API_V1}/plans",
        headers=headers,
        json={
            "public_code": "switches",
            "name": "Switches",
            "type": "BOTH",
            "traffic_limit": 100,
            "device_limit": 3,
        },
    )
    assert created.json()["allow_bonus_days"] is True
    assert created.json()["allow_promocodes"] is True

    patched = await client.patch(
        f"{API_V1}/plans/{created.json()['id']}",
        headers=headers,
        json={"allow_bonus_days": False, "allow_promocodes": False},
    )

    assert patched.status_code == 200
    assert patched.json()["allow_bonus_days"] is False
    assert patched.json()["allow_promocodes"] is False


async def test_share_urls_link_the_plan_into_the_cabinet(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_bot(token: str, proxy: object) -> None:
        return None

    monkeypatch.setattr(get_plan_share_urls, "fetch_bot_username", no_bot)
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        f"{API_V1}/plans",
        headers=headers,
        json={"name": "Shared", "type": "BOTH", "traffic_limit": 1, "device_limit": 1},
    )
    plan = created.json()

    share = await client.get(f"{API_V1}/plans/{plan['id']}/share", headers=headers)

    assert share.status_code == 200
    assert share.json()["webcabinet_url"] == (
        f"https://cabinet.example.com/purchase?plan={plan['public_code']}"
    )


async def test_catalog_leaves_trials_to_the_trial_button_but_opens_a_free_one_by_code(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner_token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    created = await client.post(
        f"{API_V1}/plans",
        headers=owner_headers,
        json={
            "name": "Trial",
            "type": "BOTH",
            "traffic_limit": 10,
            "device_limit": 1,
            "is_trial": True,
        },
    )
    plan_id = created.json()["id"]
    await client.put(
        f"{API_V1}/plans/{plan_id}/durations",
        headers=owner_headers,
        json={"durations": [{"days": 3, "order_index": 0, "base_price": "0"}]},
    )
    await client.put(
        f"{API_V1}/plans/{plan_id}/squads",
        headers=owner_headers,
        json={"internal_squads": ["11111111-1111-1111-1111-111111111111"], "external_squad": None},
    )
    await client.patch(f"{API_V1}/plans/{plan_id}", headers=owner_headers, json={"is_active": True})
    user_headers = {
        "Authorization": "Bearer "
        + await _token_for(Role.USER, user_repository, session_repository, uow, config)
    }

    listed = await client.get(f"{API_V1}/plans/catalog", headers=user_headers)
    by_code = await client.get(
        f"{API_V1}/plans/catalog",
        params={"plan_code": created.json()["public_code"]},
        headers=user_headers,
    )

    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert by_code.status_code == 200
    [plan] = by_code.json()["items"]
    assert plan["is_trial"] is True
    assert {Decimal(p["price"]) for p in plan["durations"][0]["prices"]} == {Decimal(0)}


async def test_an_id_past_the_int32_range_is_a_validation_error_not_a_crash(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/plans/3000000000", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_INVALID"
