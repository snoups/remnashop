import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
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


async def _owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login="analyticstestowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="analyticstestowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-analytics-owner"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def _admin_without_permission_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    permission: str,
) -> dict[str, str]:
    login = f"analytics-{permission.lower()}"
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=login,
                role=Role.ADMIN,
                language=Locale.EN,
                permission_revokes=[permission],
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{login}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_get_analytics_requires_admin(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/analytics/overview")
    assert response.status_code == 401


async def test_owner_can_get_analytics_for_a_period(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/overview?period_from=2026-09-01&period_to=2026-09-30", headers=headers
    )

    assert response.status_code == 200
    period = response.json()["period"]
    assert period["start"].startswith("2026-09-01")
    assert period["end"].startswith("2026-10-01")
    assert period["previous_start"].startswith("2026-08-02")


async def test_get_analytics_defaults_to_the_last_30_days(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/analytics/overview", headers=headers)

    assert response.status_code == 200
    period = response.json()["period"]
    span = datetime.datetime.fromisoformat(period["end"]) - datetime.datetime.fromisoformat(
        period["start"]
    )
    assert span == timedelta(days=30)


async def test_overview_rejects_an_inverted_period(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/overview?period_from=2026-09-30&period_to=2026-09-01", headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ANALYTICS_PERIOD_INVALID"


async def test_admin_without_analytics_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/overview", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_funnel_by_period(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/funnel?period_from=2026-09-01&period_to=2026-09-30", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["steps"]) == 4
    assert isinstance(body["by_source"], list)
    assert "previous_start" in body["period"]


async def test_get_funnel_rejects_an_inverted_period(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/funnel?period_from=2026-09-30&period_to=2026-09-01", headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ANALYTICS_PERIOD_INVALID"


async def test_admin_without_analytics_view_is_denied_on_funnel(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_FUNNEL_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/funnel", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_cohorts(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/analytics/cohorts", headers=headers)

    assert response.status_code == 200
    assert len(response.json()["items"]) == response.json()["total"] == 12


async def test_admin_without_analytics_view_is_denied_on_cohorts(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_COHORTS_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/cohorts", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_ltv_distribution(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/analytics/ltv-distribution", headers=headers)

    assert response.status_code == 200
    assert response.json()["buckets"] == []


async def test_admin_without_analytics_view_is_denied_on_ltv_distribution(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_LTV_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/ltv-distribution", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_revenue(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/revenue?period_from=2026-09-01&period_to=2026-09-07&granularity=week",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["series"]) == 1
    assert body["granularity"] == "week"
    assert body["totals"]["payments"] == 0


async def test_revenue_rejects_an_inverted_period(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/revenue?period_from=2026-09-30&period_to=2026-09-01", headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ANALYTICS_PERIOD_INVALID"


async def test_admin_without_analytics_revenue_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_REVENUE_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/revenue", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_trial(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/trial?period_from=2026-09-01&period_to=2026-09-07", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trials"] == 0 and body["trial_days"] == 7
    assert len(body["by_trial_day"]) == 11


async def test_trial_rejects_an_inverted_period(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/trial?period_from=2026-09-30&period_to=2026-09-01", headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ANALYTICS_PERIOD_INVALID"


async def test_admin_without_analytics_trial_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_TRIAL_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/trial", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_retention(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/analytics/retention", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [p["months"] for p in body["points"]] == [1, 3, 6]
    assert len(body["monthly_churn"]) == 12


async def test_admin_without_analytics_retention_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_RETENTION_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/retention", headers=headers)

    assert response.status_code == 403


async def test_admin_without_analytics_expiring_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_EXPIRING_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/retention/expiring", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_ltv_breakdown(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/analytics/ltv-breakdown", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"report_currency", "by_first_plan", "by_source", "top_payers"}


async def test_admin_without_analytics_ltv_breakdown_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_LTV_BREAKDOWN_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/ltv-breakdown", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_sources(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/sources?period_from=2026-09-01&period_to=2026-09-07", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert [c["source"] for c in body["channels"]] == ["organic", "ad_link", "referral"]
    assert body["ad_links"] == [] and body["top_referrers"] == []


async def test_admin_without_analytics_sources_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_SOURCES_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/sources", headers=headers)

    assert response.status_code == 403


async def test_owner_can_get_promocodes(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/promocodes?period_from=2026-09-01&period_to=2026-09-07",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["by_reward_type"]) == 6 and body["codes"] == []


async def test_promocodes_with_inverted_period_is_a_400(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/promocodes?period_from=2026-09-30&period_to=2026-09-01",
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ANALYTICS_PERIOD_INVALID"


async def test_admin_without_analytics_promocodes_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, "ANALYTICS_PROMOCODES_VIEW"
    )

    response = await client.get(f"{API_V1}/analytics/promocodes", headers=headers)

    assert response.status_code == 403


async def test_sources_rejects_an_inverted_period(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/analytics/sources?period_from=2026-09-30&period_to=2026-09-01", headers=headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ANALYTICS_PERIOD_INVALID"
