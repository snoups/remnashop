from pathlib import Path
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi.testclient import TestClient
from redis.asyncio import Redis

import app.api.probes_router as probes_router_module
from app.api.app import get_app
from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.plans import get_plans_providers
from app.modules.pricing import get_pricing_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscriptions_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers


@pytest.fixture
def frontend_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (assets / "index-abc123.js").write_text("console.log('bundle')")
    (dist / "index.html").write_text("<html><body>spa shell</body></html>")
    (dist / "favicon.ico").write_text("icon")
    return dist


def test_health_returns_ok(config: AppConfig, readyz_container: AsyncContainer) -> None:
    app = get_app(config)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint_exposes_prometheus_text_format(
    config: AppConfig, readyz_container: AsyncContainer
) -> None:
    app = get_app(config)
    setup_dishka(readyz_container, app)
    client = TestClient(app)
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "remnashop_http_request_duration_seconds" in response.text


async def test_metrics_is_exempt_from_the_global_rate_limit(
    config: AppConfig, readyz_container: AsyncContainer, redis: Redis
) -> None:
    app = get_app(config)
    setup_dishka(readyz_container, app)
    key = "remnashop:ratelimit:global:ip:203.0.113.23"
    await redis.delete(key)

    transport = httpx.ASGITransport(app=app, client=("203.0.113.23", 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        responses = [await client.get("/metrics") for _ in range(301)]

    assert all(r.status_code == 200 for r in responses)
    assert await redis.get(key) is None


def test_without_frontend_dist_static_routes_are_not_mounted(
    config: AppConfig, tmp_path: Path
) -> None:
    app = get_app(config, frontend_dist=tmp_path / "does-not-exist")
    client = TestClient(app)

    response = client.get("/dashboard/settings")

    assert response.status_code == 404


def test_spa_fallback_serves_index_html_for_unknown_route(
    config: AppConfig, frontend_dist: Path, readyz_container: AsyncContainer
) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    response = client.get("/dashboard/settings")

    assert response.status_code == 200
    assert "spa shell" in response.text


def test_spa_fallback_serves_real_file_at_root(
    config: AppConfig, frontend_dist: Path, readyz_container: AsyncContainer
) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.text == "icon"


def test_assets_are_served_from_assets_mount(config: AppConfig, frontend_dist: Path) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    client = TestClient(app)

    response = client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert "bundle" in response.text


@pytest.fixture
async def readyz_container(config: AppConfig) -> AsyncIterator[AsyncContainer]:
    container = make_async_container(*get_core_providers(), context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def readyz_client(
    config: AppConfig, readyz_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(readyz_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_readyz_returns_ready_when_dependencies_are_up(
    readyz_client: httpx.AsyncClient,
) -> None:
    response = await readyz_client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readyz_returns_503_when_the_database_is_unreachable(
    readyz_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Point the readiness check's DB probe at a forced failure; the route
    # must degrade to 503, not raise.
    async def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(probes_router_module, "_probe_database", _boom)

    response = await readyz_client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"status": "not ready"}


def test_spa_fallback_rejects_path_traversal_outside_frontend_dist(
    config: AppConfig, frontend_dist: Path, readyz_container: AsyncContainer
) -> None:
    secret = frontend_dist.parent / "secret.txt"
    secret.write_text("top secret host file")

    app = get_app(config, frontend_dist=frontend_dist)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    response = client.get("/%2e%2e/secret.txt")

    assert "top secret host file" not in response.text
    if response.status_code == 200:
        assert "spa shell" in response.text
    else:
        assert response.status_code in (400, 403, 404)


@pytest.fixture
async def protected_route_container(config: AppConfig) -> AsyncIterator[AsyncContainer]:
    # readyz_container only carries core providers (enough for the DB/Redis
    # probes /readyz needs) -- get_current_actor also needs UserRepository,
    # SessionRepository and ApiTokenRepository, and /plans/catalog's own
    # use_case param needs PlanRepository, so hitting that route at all
    # (even to fail with a 401) needs the fuller provider set below.
    providers = [
        *get_core_providers(),
        *get_users_providers(),
        *get_auth_providers(),
        *get_api_tokens_providers(),
        *get_plans_providers(),
        *get_pricing_providers(),
        *get_referrals_providers(),
        *get_settings_providers(),
        *get_subscriptions_providers(),
        *get_translations_providers(),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


async def test_global_rate_limit_returns_429_after_the_threshold(
    config: AppConfig, protected_route_container: AsyncContainer, redis: Redis
) -> None:
    app = get_app(config)
    setup_dishka(protected_route_container, app)
    key = "remnashop:ratelimit:global:ip:203.0.113.20"
    await redis.delete(key)

    transport = httpx.ASGITransport(app=app, client=("203.0.113.20", 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        responses = [await client.get("/api/v1/plans/catalog") for _ in range(301)]

    await redis.delete(key)

    # /plans/catalog requires an authenticated actor and this request carries
    # no token, so every response before the limit trips is 401 -- that's
    # fine, the point is proving the GLOBAL dependency (registered ahead of
    # the route's own get_current_actor in FastAPI's dependency resolution
    # order) intercepts request 301 with 429 before the route's own auth
    # check ever runs, not that the route itself succeeds.
    assert all(r.status_code != 429 for r in responses[:300])
    assert responses[300].status_code == 429


async def test_health_and_readyz_are_exempt_from_the_global_rate_limit(
    config: AppConfig, readyz_container: AsyncContainer, redis: Redis
) -> None:
    app = get_app(config)
    setup_dishka(readyz_container, app)
    key = "remnashop:ratelimit:global:ip:203.0.113.21"
    await redis.delete(key)

    transport = httpx.ASGITransport(app=app, client=("203.0.113.21", 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        responses = [await client.get("/health") for _ in range(301)]

    assert all(r.status_code == 200 for r in responses)
    assert await redis.get(key) is None


async def test_remnawave_webhook_is_exempt_from_the_global_rate_limit(
    config: AppConfig, protected_route_container: AsyncContainer, redis: Redis
) -> None:
    app = get_app(config)
    setup_dishka(protected_route_container, app)
    key = "remnashop:ratelimit:global:ip:203.0.113.22"
    await redis.delete(key)

    transport = httpx.ASGITransport(app=app, client=("203.0.113.22", 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        responses = [await client.post("/api/v1/remnawave", json={}) for _ in range(301)]

    # No valid webhook signature is sent, so the route itself rejects every
    # request -- the point is proving the global limiter never engages, not
    # that the webhook succeeds.
    assert all(r.status_code != 429 for r in responses)
    assert await redis.get(key) is None
