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
from app.core.enums import Locale, Role, SessionAudience, TransactionStatus
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.providers import get_module_providers
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import GetTransactionUseCase, ListTransactionsUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.transactions.test_repository import _order_dto


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


class _TransactionsProvider(Provider):
    scope = Scope.REQUEST

    transaction_repository = provide(TransactionRepository)
    list_transactions_use_case = provide(ListTransactionsUseCase)
    get_transaction_use_case = provide(GetTransactionUseCase)


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_module_providers(),
        _TransactionsProvider(),
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
                login="transactionsadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="transactionsadmin",
                role=Role.ADMIN,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=admin.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-transactions-admin"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(admin.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


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
