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
from app.core.enums import Locale, PaymentOrderStatus, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import get_blacklist_providers
from app.modules.passkeys import get_passkey_revoker_providers
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.usecases import GetPaymentOrderUseCase, ListPaymentOrdersUseCase
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscription_revoker_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.payments.test_repository import _order_dto


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


class _PaymentsProvider(Provider):
    scope = Scope.REQUEST

    payment_order_repository = provide(PaymentOrderRepository)
    list_payment_orders_use_case = provide(ListPaymentOrdersUseCase)
    get_payment_order_use_case = provide(GetPaymentOrderUseCase)


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
        _PaymentsProvider(),
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


@pytest.fixture
async def admin_auth_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="paymentsadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="paymentsadmin",
                role=Role.ADMIN,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=admin.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-payments-admin"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    token = create_access_token(admin.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_list_payment_orders_requires_admin(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/payments/orders")
    assert response.status_code == 401


async def test_list_payment_orders_filters_by_status(
    client: httpx.AsyncClient,
    admin_auth_headers: dict[str, str],
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="admin-router-pending")
        )
        paid = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="admin-router-paid")
        )
        await payment_order_repository.mark_status(paid.id, PaymentOrderStatus.PAID)

    response = await client.get(
        f"{API_V1}/payments/orders", params={"status": "PAID"}, headers=admin_auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == paid.id


async def test_get_payment_order_returns_the_order(
    client: httpx.AsyncClient,
    admin_auth_headers: dict[str, str],
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        created = await payment_order_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="admin-router-get")
        )

    response = await client.get(
        f"{API_V1}/payments/orders/{created.id}", headers=admin_auth_headers
    )

    assert response.status_code == 200
    assert response.json()["id"] == created.id
    assert response.json()["user"] == {
        "name": "buyer",
        "username": None,
        "telegram_id": 900_001,
        "email": None,
    }


async def test_get_payment_order_returns_404_for_a_missing_id(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    response = await client.get(f"{API_V1}/payments/orders/999999999", headers=admin_auth_headers)

    assert response.status_code == 404
