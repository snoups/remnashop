from typing import Optional

import pytest
from fastapi import HTTPException, Request
from prometheus_client import REGISTRY
from redis.asyncio import Redis as RedisClient

from app.api.dependencies.rate_limit import (
    _enforce,
    _resolve_rate_limit_identity,
    global_rate_limit,
)
from app.core.config import AppConfig
from app.core.security import create_access_token

JWT_SECRET = "test-secret-at-least-32-bytes-long-ok"
OTHER_JWT_SECRET = "a-completely-different-secret-32-bytes"


def _make_request(
    *, headers: Optional[dict[str, str]] = None, client_host: str = "203.0.113.5"
) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (client_host, 12345),
        "method": "GET",
        "path": "/",
    }
    return Request(scope)


def test_resolve_identity_falls_back_to_ip_with_no_auth_header() -> None:
    request = _make_request()

    identity = _resolve_rate_limit_identity(request, JWT_SECRET)

    assert identity == "ip:203.0.113.5"


def test_resolve_identity_falls_back_to_ip_with_malformed_token() -> None:
    request = _make_request(headers={"authorization": "Bearer not-a-real-token"})

    identity = _resolve_rate_limit_identity(request, JWT_SECRET)

    assert identity == "ip:203.0.113.5"


async def test_global_rate_limit_allows_requests_under_the_limit(
    redis: RedisClient, config: AppConfig
) -> None:
    await redis.delete(
        "remnashop:ratelimit:global:ip:203.0.113.9"
    )  # REDIS_KEY_PREFIX = "remnashop:" (app/core/constants.py)
    request = _make_request(client_host="203.0.113.9")

    await global_rate_limit.__dishka_orig_func__(request, redis, config)  # must not raise

    await redis.delete("remnashop:ratelimit:global:ip:203.0.113.9")


async def test_global_rate_limit_rejects_the_301st_request_in_one_window(
    redis: RedisClient, config: AppConfig
) -> None:
    key = "remnashop:ratelimit:global:ip:203.0.113.10"
    await redis.delete(key)
    request = _make_request(client_host="203.0.113.10")

    for _ in range(300):
        await global_rate_limit.__dishka_orig_func__(request, redis, config)

    with pytest.raises(HTTPException) as exc_info:
        await global_rate_limit.__dishka_orig_func__(request, redis, config)
    assert exc_info.value.status_code == 429

    await redis.delete(key)


async def test_global_rate_limit_skips_exempt_paths_entirely(
    redis: RedisClient, config: AppConfig
) -> None:
    scope = {
        "type": "http",
        "headers": [],
        "client": ("203.0.113.11", 12345),
        "method": "GET",
        "path": "/health",
    }
    request = Request(scope)
    key = "remnashop:ratelimit:global:ip:203.0.113.11"
    await redis.delete(key)

    for _ in range(301):
        await global_rate_limit.__dishka_orig_func__(
            request, redis, config
        )  # exempt path, must not raise

    assert await redis.get(key) is None  # never touched


def test_resolve_identity_uses_user_id_with_a_valid_token() -> None:
    token = create_access_token(user_id=42, session_id=1, secret=JWT_SECRET)
    request = _make_request(headers={"authorization": f"Bearer {token}"})

    identity = _resolve_rate_limit_identity(request, JWT_SECRET)

    assert identity == "user:42"


def test_resolve_identity_falls_back_to_ip_with_a_token_signed_by_a_different_secret() -> None:
    token = create_access_token(user_id=42, session_id=1, secret=OTHER_JWT_SECRET)
    request = _make_request(headers={"authorization": f"Bearer {token}"})

    identity = _resolve_rate_limit_identity(request, JWT_SECRET)

    assert identity == "ip:203.0.113.5"


async def test_enforce_increments_the_counter_only_on_the_rejecting_call(
    redis: RedisClient,
) -> None:
    redis_key = "remnashop:ratelimit:test-rate-limit-counter:1"
    await redis.delete(redis_key)
    before = (
        REGISTRY.get_sample_value(
            "remnashop_rate_limit_hits_total", {"key": "test-rate-limit-counter"}
        )
        or 0.0
    )

    await _enforce(redis, redis_key, 2, 60, "test-rate-limit-counter", "log label")
    await _enforce(redis, redis_key, 2, 60, "test-rate-limit-counter", "log label")
    with pytest.raises(HTTPException):
        await _enforce(redis, redis_key, 2, 60, "test-rate-limit-counter", "log label")

    after = REGISTRY.get_sample_value(
        "remnashop_rate_limit_hits_total", {"key": "test-rate-limit-counter"}
    )
    assert after == before + 1

    await redis.delete(redis_key)
