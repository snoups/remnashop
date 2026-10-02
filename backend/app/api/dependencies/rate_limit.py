from typing import Callable, Coroutine, Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, HTTPException, Request, status
from loguru import logger
from prometheus_client import Counter
from redis.asyncio import Redis

from app.api.dependencies.public import get_current_user
from app.api.errors import ApiError
from app.core.config import AppConfig
from app.core.constants import API_V1, REDIS_KEY_PREFIX, REMNAWAVE_WEBHOOK_PATH
from app.core.error_codes import ErrorCode
from app.core.security import decode_access_token
from app.core.utils.http import resolve_client_ip
from app.modules.users import UserDto

_GLOBAL_RATE_LIMIT: Final[int] = 300
_GLOBAL_RATE_LIMIT_WINDOW_S: Final[int] = 60
# Payment-gateway callbacks (/payments/{gateway}) are deliberately NOT here:
# one provider's calls share one IP bucket like the panel's do, but their
# volume is one call per payment plus retries -- nowhere near 300/min -- and
# the route is unauthenticated, so the baseline is worth keeping.
_RATE_LIMIT_EXEMPT_PATHS: Final[frozenset[str]] = frozenset(
    {"/health", "/readyz", "/metrics", f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}"}
)

RATE_LIMIT_HITS: Final[Counter] = Counter(
    "remnashop_rate_limit_hits_total",
    "Requests rejected by a rate limiter",
    labelnames=("key",),
)


async def _enforce(
    redis: Redis,
    redis_key: str,
    limit: int,
    window_seconds: int,
    key: str,
    log_label: str,
) -> None:
    current = await redis.incr(redis_key)
    # NX (not "only on current == 1") so a crash/dropped connection between
    # incr() and expire() self-heals on the next request instead of leaving
    # the key stuck with no TTL forever.
    await redis.expire(redis_key, window_seconds, nx=True)

    if current > limit:
        RATE_LIMIT_HITS.labels(key=key).inc()
        logger.warning(f"Rate limit exceeded: {log_label}")
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests, try again later",
            code=ErrorCode.RATE_LIMITED,
        )


def rate_limit(
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> Callable[[Request, Redis], Coroutine[None, None, None]]:
    @inject
    async def dependency(request: Request, redis: FromDishka[Redis]) -> None:
        client_ip = resolve_client_ip(request)
        redis_key = f"{REDIS_KEY_PREFIX}ratelimit:{key}:{client_ip}"
        await _enforce(redis, redis_key, limit, window_seconds, key, f"'{key}' by IP '{client_ip}'")

    return dependency


def user_rate_limit(
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> Callable[[Redis, UserDto], Coroutine[None, None, None]]:
    # Per account, not per IP: for a limit on what one customer may do, a
    # changed source address must not reset the budget.
    @inject
    async def dependency(
        redis: FromDishka[Redis], actor: UserDto = Depends(get_current_user)
    ) -> None:
        redis_key = f"{REDIS_KEY_PREFIX}ratelimit:{key}:user:{actor.id}"
        await _enforce(redis, redis_key, limit, window_seconds, key, f"'{key}' by user {actor.id}")

    return dependency


def _resolve_rate_limit_identity(request: Request, jwt_secret: str) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[len("Bearer ") :]
        try:
            payload = decode_access_token(token, jwt_secret)
        except Exception:  # any decode failure just falls through to IP
            pass
        else:
            return f"user:{payload.get('sub')}"
    return f"ip:{resolve_client_ip(request)}"


@inject
async def global_rate_limit(
    request: Request,
    redis: FromDishka[Redis],
    config: FromDishka[AppConfig],
) -> None:
    if request.url.path in _RATE_LIMIT_EXEMPT_PATHS:
        return

    identity = _resolve_rate_limit_identity(request, config.jwt_secret.get_secret_value())
    redis_key = f"{REDIS_KEY_PREFIX}ratelimit:global:{identity}"

    try:
        await _enforce(
            redis,
            redis_key,
            _GLOBAL_RATE_LIMIT,
            _GLOBAL_RATE_LIMIT_WINDOW_S,
            "global",
            f"global by {identity}",
        )
    except HTTPException:
        raise  # the actual 429 -- not a Redis failure, must propagate
    except Exception:  # fail open: Redis being down must not take the API down
        logger.warning("Global rate limiter failed open: Redis unavailable")
