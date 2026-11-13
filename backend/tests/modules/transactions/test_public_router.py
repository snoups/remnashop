import datetime
import json
from datetime import timedelta, timezone
from decimal import Decimal
from typing import Any, AsyncIterator
from uuid import uuid4

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, provide
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    PlanType,
    Role,
    SessionAudience,
    SubscriptionStatus,
)
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.gateways import GatewayRepository
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto, PlanSnapshot
from app.modules.transactions.gateways.base import PaymentHttpClient
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container

_YOOKASSA_REQUESTS: list[dict[str, Any]] = []


def _yookassa_payment_created(request: httpx.Request) -> httpx.Response:
    _YOOKASSA_REQUESTS.append(json.loads(request.content))
    return httpx.Response(
        200,
        json={
            "id": f"yk-payment-router-{len(_YOOKASSA_REQUESTS)}",
            "confirmation": {"confirmation_url": "https://yookassa.ru/pay/router-1"},
        },
    )


class _PaymentHttpProvider(Provider):
    scope = Scope.APP

    @provide
    def payment_http(self) -> PaymentHttpClient:
        transport = httpx.MockTransport(_yookassa_payment_created)
        return PaymentHttpClient(httpx.AsyncClient(transport=transport))


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    container = make_test_container(session, config, _PaymentHttpProvider())
    yield container
    await container.close()


@pytest.fixture
async def client(
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    app = api_app
    app.state.dishka_container = test_container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _auth_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login="checkoutrouter",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="checkoutrouter",
                role=Role.USER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-checkout"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    return await _auth_headers(user_repository, session_repository, uow, config)


@pytest.fixture
async def plan(plan_repository: PlanRepository) -> PlanDto:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="checkout-router-plan",
            name="Checkout Router Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[uuid4()], external_squad=None)
    )
    return await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))


async def test_checkout_returns_confirmation_url_for_a_valid_plan(
    client: httpx.AsyncClient,
    plan: PlanDto,
    auth_headers: dict[str, str],
    gateway_repository: GatewayRepository,
) -> None:
    await gateway_repository.update_settings(
        PaymentGatewayType.YOOKASSA, {"shop_id": "1000", "api_key": "test_key"}
    )
    await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, True)

    response = await client.post(
        f"{API_V1}/checkout",
        json={
            "plan_id": plan.id,
            "duration_days": 30,
            "currency": "RUB",
            "purchase_type": "NEW",
            "gateway_type": "YOOKASSA",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["confirmation_url"] == "https://yookassa.ru/pay/router-1"


async def test_customer_can_manage_only_their_own_auto_renewal(
    client,
    auth_headers,
    user_repository,
    subscription_repository,
    plan,
) -> None:
    user = await user_repository.find_by_login("checkoutrouter")
    subscription = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=931110,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            url="https://example.com/own-subscription",
            plan_snapshot=PlanSnapshot.from_plan(
                plan, price_paid=Decimal("500"), currency=Currency.RUB, duration_days=30
            ),
        )
    )
    url = f"{API_V1}/subscriptions/me/{subscription.id}/auto-renew"
    state = await client.get(url, headers=auth_headers)
    assert state.status_code == 200
    assert state.json()["enabled"] is False
    assert state.json()["available"] is False
    disabled = await client.put(url, json={"enabled": False}, headers=auth_headers)
    assert disabled.status_code == 200
    assert disabled.json()["customer_disabled"] is True
    enabled = await client.put(url, json={"enabled": True}, headers=auth_headers)
    assert enabled.status_code == 400
    other = await user_repository.create(CreateUserDto(name="another customer", telegram_id=931111))
    foreign = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=other.id,
            remnawave_user_id=931111,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            url="https://example.com/foreign-subscription",
            plan_snapshot=subscription.plan_snapshot,
        )
    )
    other_url = f"{API_V1}/subscriptions/me/{foreign.id}/auto-renew"
    assert (await client.get(other_url, headers=auth_headers)).status_code == 400
    assert (
        await client.put(other_url, json={"enabled": False}, headers=auth_headers)
    ).status_code == 400


async def test_checkout_rejects_a_currency_the_gateway_does_not_settle(
    client: httpx.AsyncClient, plan: PlanDto, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_V1}/checkout",
        json={
            "plan_id": plan.id,
            "duration_days": 30,
            "currency": "USD",
            "purchase_type": "NEW",
            "gateway_type": "YOOKASSA",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


async def test_checkout_requires_authentication(client: httpx.AsyncClient, plan: PlanDto) -> None:
    response = await client.post(
        f"{API_V1}/checkout",
        json={
            "plan_id": plan.id,
            "duration_days": 30,
            "currency": "RUB",
            "purchase_type": "NEW",
            "gateway_type": "YOOKASSA",
        },
    )

    assert response.status_code == 401


async def test_quote_returns_the_price_breakdown(
    client: httpx.AsyncClient, plan: PlanDto, auth_headers: dict[str, str]
) -> None:
    body = {"plan_id": plan.id, "duration_days": 30, "currency": "RUB"}

    response = await client.post(f"{API_V1}/checkout/quote", json=body, headers=auth_headers)

    assert response.status_code == 200
    assert set(response.json()) == {
        "base_price",
        "plan_discount_percent",
        "discount_percent",
        "discount_source",
        "final_price",
        "currency",
    }
    assert (await client.post(f"{API_V1}/checkout/quote", json=body)).status_code == 401


async def _customer_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    name: str,
    audience: SessionAudience,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(CreateUserDto(name=name, language=Locale.EN))
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"txn-{name}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=audience,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def _enable_yookassa(gateway_repository: GatewayRepository) -> None:
    await gateway_repository.update_settings(
        PaymentGatewayType.YOOKASSA, {"shop_id": "1000", "api_key": "test_key"}
    )
    await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, True)


def _checkout_body(plan: PlanDto) -> dict[str, object]:
    return {
        "plan_id": plan.id,
        "duration_days": 30,
        "currency": "RUB",
        "purchase_type": "NEW",
        "gateway_type": "YOOKASSA",
    }


async def test_a_cabinet_checkout_returns_to_the_cabinet(
    client: httpx.AsyncClient,
    plan: PlanDto,
    gateway_repository: GatewayRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    await _enable_yookassa(gateway_repository)
    cabinet = await _customer_headers(
        user_repository, session_repository, uow, config, "cab-buyer", SessionAudience.CABINET
    )
    _YOOKASSA_REQUESTS.clear()

    response = await client.post(f"{API_V1}/checkout", json=_checkout_body(plan), headers=cabinet)

    assert response.status_code == 201
    order_id = response.json()["order_id"]
    assert _YOOKASSA_REQUESTS[-1]["confirmation"]["return_url"] == (
        f"https://cabinet.example.com/payment/result?order_id={order_id}"
    )


async def test_a_dashboard_checkout_keeps_the_old_return_address(
    client: httpx.AsyncClient,
    plan: PlanDto,
    gateway_repository: GatewayRepository,
    auth_headers: dict[str, str],
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", "cabinet.example.com")
    await _enable_yookassa(gateway_repository)
    _YOOKASSA_REQUESTS.clear()

    response = await client.post(
        f"{API_V1}/checkout", json=_checkout_body(plan), headers=auth_headers
    )

    assert response.status_code == 201
    assert _YOOKASSA_REQUESTS[-1]["confirmation"]["return_url"] == (
        f"https://{config.domain.get_secret_value()}"
    )


async def test_own_transactions_list_and_detail(
    client: httpx.AsyncClient,
    plan: PlanDto,
    gateway_repository: GatewayRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    await _enable_yookassa(gateway_repository)
    mine = await _customer_headers(
        user_repository, session_repository, uow, config, "txn-mine", SessionAudience.CABINET
    )
    theirs = await _customer_headers(
        user_repository, session_repository, uow, config, "txn-theirs", SessionAudience.CABINET
    )
    own_order = (
        await client.post(f"{API_V1}/checkout", json=_checkout_body(plan), headers=mine)
    ).json()["order_id"]
    foreign_order = (
        await client.post(f"{API_V1}/checkout", json=_checkout_body(plan), headers=theirs)
    ).json()["order_id"]

    listed = await client.get(f"{API_V1}/transactions/me", headers=mine)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [own_order]
    assert listed.json()["items"][0]["plan_name"] == plan.name
    # "try again" reopens the same plan; a new purchase targets no subscription
    assert listed.json()["items"][0]["plan_id"] == plan.id
    assert listed.json()["items"][0]["target_subscription_id"] is None
    # no discount on this order: the base price is the final one
    item = listed.json()["items"][0]
    assert item["base_price"] == item["final_price"]
    assert (item["plan_discount_percent"], item["discount_percent"]) == (0, 0)
    assert item["discount_source"] == "NONE"

    assert (
        await client.get(f"{API_V1}/transactions/me/{own_order}", headers=mine)
    ).status_code == 200
    foreign = await client.get(f"{API_V1}/transactions/me/{foreign_order}", headers=mine)
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "PAYMENT_ORDER_NOT_FOUND"

    assert (await client.get(f"{API_V1}/checkout/methods", headers=mine)).status_code == 200
