import datetime
from dataclasses import replace
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, provide
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.models import User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    Role,
    SessionAudience,
    TransactionStatus,
)
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.settings import SettingsRepository
from app.modules.settings.dto import UpdateBotSettingsDto
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import GetTransactionUseCase, ListTransactionsUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container
from tests.modules.transactions.test_repository import _order_dto


class _TransactionsProvider(Provider):
    scope = Scope.REQUEST

    transaction_repository = provide(TransactionRepository)
    list_transactions_use_case = provide(ListTransactionsUseCase)
    get_transaction_use_case = provide(GetTransactionUseCase)


class _RefundingGateway:
    async def refund(self, charge_id: str, telegram_id: int) -> None:
        return None


class _FakeGatewayFactory(PaymentGatewayFactory):
    def __init__(self) -> None:
        pass

    def build(self, gateway_type, settings):  # type: ignore[no-untyped-def]
        return _RefundingGateway()  # type: ignore[return-value]


class _GatewayFactoryProvider(Provider):
    @provide(scope=Scope.APP)
    def gateway_factory(self) -> PaymentGatewayFactory:
        return _FakeGatewayFactory()


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    container = make_test_container(
        session, config, _TransactionsProvider(), _GatewayFactoryProvider()
    )
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
    role: Role,
) -> dict[str, str]:
    login = f"transactions{role.name.lower()}"
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=login,
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=admin.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{login}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(admin.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_auth_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    return await _auth_headers(user_repository, session_repository, uow, config, Role.ADMIN)


@pytest.fixture
async def owner_auth_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    return await _auth_headers(user_repository, session_repository, uow, config, Role.OWNER)


async def test_list_transactions_requires_admin(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/transactions")
    assert response.status_code == 401


async def test_list_transactions_filters_by_status(
    client: httpx.AsyncClient,
    admin_auth_headers: dict[str, str],
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="admin-router-pending")
        )
        paid = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="admin-router-paid")
        )
        await transaction_repository.mark_status(paid.id, TransactionStatus.PAID)

    response = await client.get(
        f"{API_V1}/transactions", params={"status": "PAID"}, headers=admin_auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == paid.id


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/transactions", {"user_id": "99999999999"}),
        ("/transactions/summary", {"user_id": "99999999999"}),
        ("/transactions/summary", {"subscription_id": "99999999999"}),
    ],
)
async def test_out_of_range_ids_are_rejected_not_crashing(
    client: httpx.AsyncClient,
    admin_auth_headers: dict[str, str],
    path: str,
    params: dict[str, str],
) -> None:
    response = await client.get(f"{API_V1}{path}", params=params, headers=admin_auth_headers)

    assert response.status_code == 422


async def test_get_transaction_returns_the_order(
    client: httpx.AsyncClient,
    admin_auth_headers: dict[str, str],
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="admin-router-get")
        )

    response = await client.get(f"{API_V1}/transactions/{created.id}", headers=admin_auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created.id
    assert response.json()["is_test"] is False
    assert response.json()["channel"] == "CABINET"
    assert response.json()["user"] == {
        "name": "buyer",
        "username": None,
        "telegram_id": 900_001,
        "email": None,
    }


async def test_get_transaction_returns_404_for_a_missing_id(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    response = await client.get(f"{API_V1}/transactions/999999999", headers=admin_auth_headers)

    assert response.status_code == 404


async def _paid_stars_order(
    transaction_repository: TransactionRepository, uow: UnitOfWork, user_id: int, plan_id: int
) -> int:
    async with uow:
        created = await transaction_repository.create(
            replace(
                _order_dto(user_id=user_id, plan_id=plan_id, idempotency_key="admin-router-refund"),
                gateway_type=PaymentGatewayType.TELEGRAM_STARS,
                currency=Currency.XTR,
            )
        )
        await transaction_repository.mark_status(
            created.id, TransactionStatus.PAID, external_payment_id="router-charge"
        )
    return created.id


async def test_refund_routes_need_the_refund_permission(
    client: httpx.AsyncClient,
    admin_auth_headers: dict[str, str],
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    order_id = await _paid_stars_order(transaction_repository, uow, user_id, plan_id)

    preview = await client.get(
        f"{API_V1}/transactions/{order_id}/refund-preview", headers=admin_auth_headers
    )
    refund = await client.post(
        f"{API_V1}/transactions/{order_id}/actions/refund",
        json={"rollback_subscription": False},
        headers=admin_auth_headers,
    )

    assert preview.status_code == 403
    assert refund.status_code == 403


async def test_owner_previews_and_refunds_a_stars_order(
    client: httpx.AsyncClient,
    owner_auth_headers: dict[str, str],
    transaction_repository: TransactionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
) -> None:
    order_id = await _paid_stars_order(transaction_repository, uow, user_id, plan_id)
    async with uow:
        await settings_repository.update_bot_settings(UpdateBotSettingsDto(token="123:abc"))

    preview = await client.get(
        f"{API_V1}/transactions/{order_id}/refund-preview", headers=owner_auth_headers
    )
    refund = await client.post(
        f"{API_V1}/transactions/{order_id}/actions/refund",
        json={"rollback_subscription": False},
        headers=owner_auth_headers,
    )

    assert preview.status_code == 200
    assert preview.json() == {
        "refundable": True,
        "reason": None,
        "rollback": {
            "available": False,
            "blocked_reason": "not_provisioned",
            "old_term_expired": False,
        },
    }
    assert refund.status_code == 200
    assert refund.json()["rollback_failed"] is False
    assert refund.json()["transaction"]["status"] == "REFUNDED"


async def test_recurring_dashboard_is_available_to_an_owner(client, owner_auth_headers):
    response = await client.get(f"{API_V1}/transactions/recurring", headers=owner_auth_headers)
    assert response.status_code == 200
    assert response.json()["summary"]["total"] == 0
    assert response.json()["items"] == []
    assert response.json()["summary"]["revenue"] == "0"


async def test_recurring_dashboard_requires_recurring_permission(
    client,
    admin_auth_headers,
    user_repository,
    session,
    uow,
):
    admin = await user_repository.find_by_login("transactionsadmin")
    async with uow:
        row = await session.get(User, admin.id)
        row.permission_revokes = ["TRANSACTIONS_RECURRING_VIEW"]
        await session.flush()
    response = await client.get(f"{API_V1}/transactions/recurring", headers=admin_auth_headers)
    assert response.status_code == 403


async def test_recurring_dashboard_rejects_unknown_state(client, owner_auth_headers):
    response = await client.get(
        f"{API_V1}/transactions/recurring?state=secret", headers=owner_auth_headers
    )
    assert response.status_code == 422


async def test_recurring_permission_does_not_require_other_transaction_permissions(
    client,
    admin_auth_headers,
    user_repository,
    session,
    uow,
):
    admin = await user_repository.find_by_login("transactionsadmin")
    async with uow:
        row = await session.get(User, admin.id)
        row.permission_revokes = ["TRANSACTIONS_VIEW", "TRANSACTIONS_SUMMARY_VIEW"]
        await session.flush()
    response = await client.get(f"{API_V1}/transactions/recurring", headers=admin_auth_headers)
    assert response.status_code == 200
    assert (
        await client.get(f"{API_V1}/transactions", headers=admin_auth_headers)
    ).status_code == 403
    assert (
        await client.get(f"{API_V1}/transactions/summary", headers=admin_auth_headers)
    ).status_code == 403
