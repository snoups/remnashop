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
from app.core.security.permissions import Permission
from app.modules.advertising.repository import AdLinkRepository
from app.modules.advertising.usecases import (
    CreateAdLinkUseCase,
    DeleteAdLinkUseCase,
    GenerateAdLinkCodeUseCase,
    GetAdLinkStatsUseCase,
    GetAdvertisingSummaryUseCase,
    ListAdLinkAttributedUsersUseCase,
    ListAdLinksUseCase,
    UpdateAdLinkUseCase,
)
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import get_blacklist_providers
from app.modules.passkeys import get_passkey_revoker_providers
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscription_revoker_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


class _AdvertisingProvider(Provider):
    scope = Scope.REQUEST

    ad_link_repository = provide(AdLinkRepository)
    payment_order_repository = provide(PaymentOrderRepository)
    pricing_repository = provide(PricingRepository)
    create_ad_link_use_case = provide(CreateAdLinkUseCase)
    update_ad_link_use_case = provide(UpdateAdLinkUseCase)
    delete_ad_link_use_case = provide(DeleteAdLinkUseCase)
    list_ad_links_use_case = provide(ListAdLinksUseCase)
    generate_ad_link_code_use_case = provide(GenerateAdLinkCodeUseCase)
    get_ad_link_stats_use_case = provide(GetAdLinkStatsUseCase)
    get_advertising_summary_use_case = provide(GetAdvertisingSummaryUseCase)
    list_ad_link_attributed_users_use_case = provide(ListAdLinkAttributedUsersUseCase)


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
        _AdvertisingProvider(),
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
                login="advertisingadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="advertisingadmin",
                role=Role.ADMIN,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=admin.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-advertising-admin"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    token = create_access_token(admin.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_list_ad_links_requires_admin(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/advertising/links")
    assert response.status_code == 401


async def test_create_and_list_ad_link(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    create_response = await client.post(
        f"{API_V1}/advertising/links",
        json={"name": "YouTube", "code": "router-yt-1"},
        headers=admin_auth_headers,
    )
    assert create_response.status_code == 201
    assert create_response.json()["code"] == "router-yt-1"

    list_response = await client.get(f"{API_V1}/advertising/links", headers=admin_auth_headers)
    assert list_response.status_code == 200
    codes = {item["code"] for item in list_response.json()["items"]}
    assert "router-yt-1" in codes


async def test_create_ad_link_duplicate_code_returns_409(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    await client.post(
        f"{API_V1}/advertising/links",
        json={"name": "A", "code": "router-dup"},
        headers=admin_auth_headers,
    )
    response = await client.post(
        f"{API_V1}/advertising/links",
        json={"name": "B", "code": "router-dup"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 409


async def test_create_ad_link_via_api_token_stores_null_created_by(
    client: httpx.AsyncClient,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
) -> None:
    secret = "advertising-router-token-secret"
    async with uow:
        await api_token_repository.create(
            CreateApiTokenDto(
                name="ci",
                permissions=[Permission.AD_LINKS_CREATE, Permission.AD_LINKS_VIEW],
                token_hash=hash_refresh_token(secret),
                created_by_user_id=None,
                expires_at=None,
            )
        )
        await uow.commit()

    response = await client.post(
        f"{API_V1}/advertising/links",
        json={"name": "TokenLink", "code": "router-token-1"},
        headers={"Authorization": f"Bearer {secret}"},
    )

    assert response.status_code == 201
    assert response.json()["created_by"] is None


async def test_create_ad_link_rejects_code_longer_than_48(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_V1}/advertising/links",
        json={"name": "Long", "code": "a" * 49},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422


async def test_get_stats_for_unknown_ad_link_returns_404(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    response = await client.get(
        f"{API_V1}/advertising/links/999999/stats", headers=admin_auth_headers
    )
    assert response.status_code == 404


async def test_get_summary_returns_totals_and_per_link_metrics(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        f"{API_V1}/advertising/links",
        json={"name": "Summary", "code": "summary-router", "cost": "50"},
        headers=admin_auth_headers,
    )
    assert created.status_code == 201

    response = await client.get(
        f"{API_V1}/advertising/summary",
        params={"created_from": "2020-01-01T00:00:00Z"},
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attributions_count"] == 0
    assert body["roi"] is not None
    assert [link["ad_link_id"] for link in body["links"]] == [created.json()["id"]]
