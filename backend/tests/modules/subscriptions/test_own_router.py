import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import AccessMode, SessionAudience
from app.core.security import create_access_token, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.settings.dto import UpdateAccessSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container
from tests.modules.subscriptions.factories import create_subscription


@pytest.fixture
async def client(
    session: AsyncSession, config: AppConfig, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    container = make_test_container(session, config)
    app = api_app
    app.state.dishka_container = container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await container.close()


async def _bearer(
    user_id: int, session_repository: SessionRepository, config: AppConfig
) -> dict[str, str]:
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(f"own-subs-{user_id}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.CABINET,
        )
    )
    token = create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_lists_only_own_active_subscriptions(
    client: httpx.AsyncClient,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    mine = await create_subscription(
        subscription_repository, user_repository, telegram_id=77001, remnawave_user_id=77001
    )
    await create_subscription(
        subscription_repository, user_repository, telegram_id=77002, remnawave_user_id=77002
    )
    headers = await _bearer(mine.user_id, session_repository, config)

    response = await client.get(f"{API_V1}/subscriptions/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == mine.id
    assert item["url"] == mine.url
    assert item["plan_name"] == mine.plan_snapshot.name
    assert item["plan_id"] == mine.plan_snapshot.plan_id
    # no panel in router tests: the lookup fails and degrades to None
    assert item["used_traffic"] is None


async def test_the_connect_signature_vouches_for_its_own_link_only(
    client: httpx.AsyncClient,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    mine = await create_subscription(
        subscription_repository, user_repository, telegram_id=77003, remnawave_user_id=77003
    )
    headers = await _bearer(mine.user_id, session_repository, config)
    item = (await client.get(f"{API_V1}/subscriptions/me", headers=headers)).json()["items"][0]

    def digest(url: str) -> str:
        return base64.urlsafe_b64encode(hashlib.sha256(url.encode()).digest()).rstrip(b"=").decode()

    async def verify(body: dict[str, str]) -> httpx.Response:
        # no session: the page asking runs in a browser that never signed in
        return await client.post(f"{API_V1}/shop/connect-guide/verify", json=body)

    signature = item["connect_signature"]
    ok = await verify({"digest": digest(item["url"]), "signature": signature})
    assert ok.status_code == 200
    assert ok.json() == {"valid": True}
    assert ok.headers["cache-control"] == "no-store"

    forged = await verify({"digest": digest("https://evil.example/sub"), "signature": signature})
    assert forged.json() == {"valid": False}
    # a link sent along is refused outright: the page never sends one
    leaked = await verify(
        {"digest": digest(item["url"]), "signature": signature, "url": item["url"]}
    )
    assert leaked.status_code == 422


async def test_a_foreign_subscription_is_refused_like_a_missing_one(
    client: httpx.AsyncClient,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    mine = await create_subscription(
        subscription_repository, user_repository, telegram_id=77011, remnawave_user_id=77011
    )
    theirs = await create_subscription(
        subscription_repository, user_repository, telegram_id=77012, remnawave_user_id=77012
    )
    headers = await _bearer(mine.user_id, session_repository, config)

    for method, path in (
        ("GET", f"/subscriptions/me/{theirs.id}/devices"),
        ("DELETE", f"/subscriptions/me/{theirs.id}/devices/abc"),
        ("POST", f"/subscriptions/me/{theirs.id}/devices/bulk/delete"),
        ("POST", f"/subscriptions/me/{theirs.id}/actions/reissue"),
    ):
        response = await client.request(method, f"{API_V1}{path}", headers=headers)
        # the bot's usecases answer a foreign id like a missing one, so ids can't be probed
        assert response.status_code == 400, path
        assert response.json()["code"] == "TARGET_SUBSCRIPTION_NOT_OWNED", path


async def test_trial_availability_and_auth(
    client: httpx.AsyncClient,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    config: AppConfig,
) -> None:
    assert (await client.get(f"{API_V1}/subscriptions/me")).status_code == 401

    mine = await create_subscription(
        subscription_repository, user_repository, telegram_id=77021, remnawave_user_id=77021
    )
    headers = await _bearer(mine.user_id, session_repository, config)
    trial = await client.get(f"{API_V1}/subscriptions/me/trial", headers=headers)
    assert trial.status_code == 200
    assert trial.json()["is_available"] is False  # no trial plan configured in this test

    activate = await client.post(
        f"{API_V1}/subscriptions/me/actions/activate-trial", headers=headers
    )
    assert activate.status_code == 400
    assert activate.json()["code"] == "TRIAL_NOT_AVAILABLE"


async def test_new_customer_routes_are_closed_in_restricted_mode(
    client: httpx.AsyncClient,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    mine = await create_subscription(
        subscription_repository, user_repository, telegram_id=77031, remnawave_user_id=77031
    )
    headers = await _bearer(mine.user_id, session_repository, config)
    async with uow:
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(mode=AccessMode.RESTRICTED)
        )
        await uow.commit()

    for path in (
        "/subscriptions/me",
        "/subscriptions/me/trial",
        "/transactions/me",
        "/checkout/methods",
    ):
        response = await client.get(f"{API_V1}{path}", headers=headers)
        assert response.status_code == 403, path
        assert response.json()["code"] == "ACCESS_RESTRICTED", path


async def test_a_cabinet_session_cannot_read_the_build_metadata(
    client: httpx.AsyncClient,
    session_repository: SessionRepository,
    user_repository: UserRepository,
    config: AppConfig,
) -> None:
    customer = await user_repository.create(CreateUserDto(name="curious", telegram_id=95_001))

    response = await client.get(
        f"{API_V1}/system/metadata",
        headers=await _bearer(customer.id, session_repository, config),
    )

    assert response.status_code == 403
