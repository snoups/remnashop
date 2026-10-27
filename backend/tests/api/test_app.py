from datetime import timedelta
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx
import pytest
from dishka import AsyncContainer, make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi.testclient import TestClient
from loguru import logger
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.probes_router as probes_router_module
from app.api.app import get_app
from app.api.middlewares import BodySizeLimitMiddleware
from app.core.config import AppConfig
from app.core.constants import API_V1, DOCS_PATH
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_docs_token, hash_refresh_token
from app.core.utils.time import datetime_now
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.providers import get_module_providers
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container


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


def test_metrics_endpoint_is_absent_by_default(
    config: AppConfig, readyz_container: AsyncContainer
) -> None:
    app = get_app(config.model_copy(update={"metrics_enabled": False}))
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    assert client.get("/metrics").status_code == 404


def test_metrics_endpoint_exposes_prometheus_text_format(
    config: AppConfig, readyz_container: AsyncContainer
) -> None:
    app = get_app(config.model_copy(update={"metrics_enabled": True}))
    setup_dishka(readyz_container, app)
    client = TestClient(app)
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "remnashop_http_request_duration_seconds" in response.text


async def test_metrics_is_exempt_from_the_global_rate_limit(
    config: AppConfig, readyz_container: AsyncContainer, redis: Redis
) -> None:
    app = get_app(config.model_copy(update={"metrics_enabled": True}))
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


def test_assets_are_gzipped_and_cached_forever(config: AppConfig, frontend_dist: Path) -> None:
    (frontend_dist / "assets" / "big-def456.js").write_text("console.log('x');" * 200)
    app = get_app(config, frontend_dist=frontend_dist)
    client = TestClient(app)

    response = client.get("/assets/big-def456.js", headers={"Accept-Encoding": "gzip"})

    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_index_html_is_always_revalidated(
    config: AppConfig, frontend_dist: Path, readyz_container: AsyncContainer
) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    response = client.get("/dashboard/settings")

    assert response.headers["cache-control"] == "no-cache"


@pytest.fixture
async def readyz_container(config: AppConfig) -> AsyncIterator[AsyncContainer]:
    container = make_async_container(
        *get_core_providers(), *get_module_providers(), context={AppConfig: config}
    )
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
    # readyz_container has only core providers; even a 401 from /plans/catalog
    # needs get_current_actor's repositories and PlanRepository
    providers = [
        *get_core_providers(),
        *get_module_providers(),
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

    # no token, so every response is 401 until the limit trips: the global
    # dependency runs before the route's auth and answers request 301 with 429
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

    # unsigned, so the route rejects every request; what matters is that the
    # global limiter never answers
    assert all(r.status_code != 429 for r in responses)
    assert await redis.get(key) is None


def test_spa_and_api_responses_carry_anti_framing_headers(
    config: AppConfig, frontend_dist: Path, readyz_container: AsyncContainer
) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    for path in ("/dashboard/users", "/health"):
        response = client.get(path)
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "same-origin"
        assert "camera=()" in response.headers["permissions-policy"]
        assert response.headers["strict-transport-security"] == "max-age=31536000"


def test_only_the_spa_gets_the_script_policy(
    config: AppConfig, frontend_dist: Path, readyz_container: AsyncContainer
) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    assert "script-src 'self'" in client.get("/dashboard/users").headers["content-security-policy"]
    assert client.get("/health").headers["content-security-policy"] == "frame-ancestors 'none'"


async def _multipart_chunks(total: int):
    # a well-formed file part, so the form parser keeps spooling it
    yield (
        b'--b\r\nContent-Disposition: form-data; name="file"; filename="a.png"\r\n'
        b"Content-Type: image/png\r\n\r\n"
    )
    chunk = b"x" * 65536
    sent = 0
    while sent < total:
        yield chunk
        sent += len(chunk)


@pytest.mark.parametrize(
    ("method", "path", "too_big"),
    [
        ("POST", "/api/v1/auth/login", 2 * 1024 * 1024),
        ("PUT", "/api/v1/banners/menu/ru", 7 * 1024 * 1024),
    ],
)
async def test_oversized_body_is_rejected_before_authentication(
    config: AppConfig, readyz_container: AsyncContainer, method: str, path: str, too_big: int
) -> None:
    app = get_app(config)
    setup_dishka(readyz_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        declared = await client.request(method, path, content=b"x" * too_big)
        # chunked: no Content-Length, the stream itself has to be cut off
        streamed = await client.request(
            method,
            path,
            content=_multipart_chunks(too_big),
            headers={"Content-Type": "multipart/form-data; boundary=b"},
        )

    for response in (declared, streamed):
        assert response.status_code == 413
        assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


async def test_upload_route_allows_bodies_above_the_default_limit() -> None:
    received: list[int] = []

    async def echo(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        size = 0
        more = True
        while more:
            message = await receive()
            size += len(message.get("body", b""))
            more = message.get("more_body", False)
        received.append(size)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    transport = httpx.ASGITransport(app=BodySizeLimitMiddleware(echo))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        upload = await client.put("/api/v1/banners/menu/ru", content=b"x" * (2 * 1024 * 1024))
        other = await client.post("/api/v1/plans", content=b"x" * (2 * 1024 * 1024))

    assert upload.status_code == 200
    assert received == [2 * 1024 * 1024]
    assert other.status_code == 413


async def test_broadcast_media_route_allows_bodies_up_to_its_media_limit() -> None:
    async def drain(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        more = True
        while more:
            message = await receive()
            more = message.get("more_body", False)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    transport = httpx.ASGITransport(app=BodySizeLimitMiddleware(drain))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        video = await client.put("/api/v1/broadcasts/7/media", content=b"x" * (12 * 1024 * 1024))
        huge = await client.put("/api/v1/broadcasts/7/media", content=b"x" * (60 * 1024 * 1024))
        other = await client.put("/api/v1/broadcasts/7", content=b"x" * (2 * 1024 * 1024))

    assert video.status_code == 200
    assert huge.status_code == 413
    assert other.status_code == 413


def test_docs_refuse_a_request_without_a_ticket(
    config: AppConfig, readyz_container: AsyncContainer
) -> None:
    app = get_app(config)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    for path in (DOCS_PATH, f"{DOCS_PATH}/redoc", f"{DOCS_PATH}/openapi.json"):
        assert client.get(path).status_code == 401
    assert client.get(DOCS_PATH, params={"ott": "forged"}).status_code == 401


async def test_docs_trade_a_ticket_for_a_cookie_tied_to_the_session(
    config: AppConfig,
    session: AsyncSession,
    user_repository: UserRepository,
    session_repository: SessionRepository,
) -> None:
    owner = await user_repository.create(
        CreateUserDto(name="docs", login="docs-owner", role=Role.ADMIN, language=Locale.EN)
    )
    dashboard = await session_repository.create(
        CreateSessionDto(
            user_id=owner.id,
            refresh_token_hash=hash_refresh_token("docs-refresh"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime_now() + timedelta(days=1),
            audience=SessionAudience.DASHBOARD,
        )
    )
    container = make_test_container(session, config)
    app = get_app(config)
    setup_dishka(container, app)
    secret = config.jwt_secret.get_secret_value()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        # an access-scoped token is not a ticket
        leaked_cookie = create_docs_token("access", 60, secret, dashboard.id)
        assert (await client.get(DOCS_PATH, params={"ott": leaked_cookie})).status_code == 401

        ott = create_docs_token("ott", 30, secret, dashboard.id)
        redirect = await client.get(DOCS_PATH, params={"ott": ott})
        assert redirect.status_code == 303
        assert redirect.headers["location"] == DOCS_PATH

        # spent: a second exchange of the same ticket fails
        assert (await client.get(DOCS_PATH, params={"ott": ott})).status_code == 401

        assert (await client.get(DOCS_PATH)).status_code == 200
        schema = await client.get(f"{DOCS_PATH}/openapi.json")
        assert schema.status_code == 200
        assert f"{API_V1}/api-tokens" in schema.json()["paths"]

        # signing out of the dashboard closes the docs too
        await session_repository.revoke_by_id(dashboard.id)
        assert (await client.get(f"{DOCS_PATH}/openapi.json")).status_code == 401
    await container.close()


async def test_emoji_art_counts_in_its_own_bucket_not_the_ip_budget(
    config: AppConfig, protected_route_container: AsyncContainer, redis: Redis
) -> None:
    app = get_app(config)
    setup_dishka(protected_route_container, app)
    global_key = "remnashop:ratelimit:global:ip:203.0.113.23"
    emoji_key = "remnashop:ratelimit:emoji:ip:203.0.113.23"
    await redis.delete(global_key, emoji_key)

    transport = httpx.ASGITransport(app=app, client=("203.0.113.23", 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        responses = [await client.get(f"/api/v1/emoji-packs/thumbnails/{n}") for n in range(301)]

    assert all(r.status_code != 429 for r in responses)
    assert await redis.get(global_key) is None
    assert int(await redis.get(emoji_key)) == 301

    # an admin's DELETE is not art: it counts in the ordinary bucket
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.delete("/api/v1/emoji-packs/some-set")
    assert int(await redis.get(global_key)) == 1
    await redis.delete(global_key)
    await redis.delete(emoji_key)


def test_an_unknown_api_path_is_a_json_404_not_the_spa(
    config: AppConfig, frontend_dist: Path, readyz_container: AsyncContainer
) -> None:
    app = get_app(config, frontend_dist=frontend_dist)
    setup_dishka(readyz_container, app)
    client = TestClient(app)

    unknown_get = client.get("/api/v1/no-such-thing")
    unknown_post = client.post("/api/v1/no-such-thing", json={})
    spa = client.get("/dashboard/users")

    assert unknown_get.status_code == 404
    assert unknown_get.json()["code"] == "NOT_FOUND"
    assert unknown_get.headers["cache-control"] == "no-store"
    assert unknown_post.status_code == 404
    assert spa.status_code == 200
    assert "text/html" in spa.headers["content-type"]


@pytest.mark.parametrize(
    ("domain", "secret", "warned"),
    [
        ("cabinet.example.com", None, True),
        ("cabinet.example.com", "short", True),
        ("cabinet.example.com", "x" * 32, False),
        (None, None, False),
    ],
)
def test_weak_or_missing_cabinet_proxy_secret_is_warned_about(
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
    domain: Optional[str],
    secret: Optional[str],
    warned: bool,
) -> None:
    monkeypatch.setattr(config.cabinet, "domain", domain)
    monkeypatch.setattr(config.cabinet, "proxy_secret", SecretStr(secret) if secret else None)
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="WARNING")
    try:
        get_app(config)
    finally:
        logger.remove(sink)
    assert any("CABINET_PROXY_SECRET" in message for message in messages) is warned
