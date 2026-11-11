from typing import AsyncIterator, Callable, Coroutine, Final

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
from app.core.utils.http import ip_rate_bucket, resolve_client_ip
from app.core.utils.rate_counter import hit_counter, release_counter, user_rate_key
from app.modules.users import UserDto

_GLOBAL_RATE_LIMIT: Final[int] = 300
_GLOBAL_RATE_LIMIT_WINDOW_S: Final[int] = 60
# emoji art loads by <img> with no token, a whole pack at once (up to ~400
# files): its own bucket, so it doesn't eat the IP's budget for the API
_EMOJI_PREFIX: Final[str] = f"{API_V1}/emoji-packs/"
_EMOJI_RATE_LIMIT: Final[int] = 3000
# Payment-gateway callbacks (/payments/{gateway}) stay limited: one call per
# payment plus retries is far below 300/min, and the route is unauthenticated.
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
    current = await hit_counter(redis, redis_key, window_seconds)

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
        client_ip = ip_rate_bucket(resolve_client_ip(request))
        redis_key = f"{REDIS_KEY_PREFIX}ratelimit:{key}:{client_ip}"
        await _enforce(redis, redis_key, limit, window_seconds, key, f"'{key}' by IP '{client_ip}'")

    return dependency


class FailureLimit:
    def __init__(self) -> None:
        self.failed = False

    async def record_failure(self) -> None:
        self.failed = True


def failure_rate_limit(
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> Callable[[Request, Redis], AsyncIterator[FailureLimit]]:
    # Keeps only attempts the route reports through record_failure(): hundreds
    # of customers share one VPN exit IP, and their successful sign-ins must
    # not eat the budget of the next one. Each attempt is counted before it
    # runs and given back unless it failed, so a burst of parallel guesses
    # can't all pass a check made before any of them was counted.
    @inject
    async def dependency(request: Request, redis: FromDishka[Redis]) -> AsyncIterator[FailureLimit]:
        client_ip = ip_rate_bucket(resolve_client_ip(request))
        redis_key = f"{REDIS_KEY_PREFIX}ratelimit:{key}:{client_ip}"
        if await hit_counter(redis, redis_key, window_seconds) > limit:
            RATE_LIMIT_HITS.labels(key=key).inc()
            logger.warning(f"Rate limit exceeded: '{key}' by IP '{client_ip}'")
            raise ApiError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests, try again later",
                code=ErrorCode.RATE_LIMITED,
            )
        guard = FailureLimit()
        try:
            yield guard
        finally:
            if not guard.failed:
                await release_counter(redis, redis_key)

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
        redis_key = user_rate_key(key, actor.id)
        await _enforce(redis, redis_key, limit, window_seconds, key, f"'{key}' by user {actor.id}")

    return dependency


def _resolve_rate_limit_identity(request: Request, jwt_secret: str) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[len("Bearer ") :]
        try:
            payload = decode_access_token(token, jwt_secret)
        except Exception:  # any decode failure falls through to IP
            pass
        else:
            return f"user:{payload.get('sub')}"
    return f"ip:{ip_rate_bucket(resolve_client_ip(request))}"


@inject
async def global_rate_limit(
    request: Request,
    redis: FromDishka[Redis],
    config: FromDishka[AppConfig],
) -> None:
    # the routed path: request.url is rebuilt from the Host header
    path: str = request.scope["path"]
    if path in _RATE_LIMIT_EXEMPT_PATHS:
        return

    # only the art loads: an admin's DELETE stays in the ordinary bucket
    if request.method == "GET" and path.startswith(_EMOJI_PREFIX):
        identity = f"ip:{ip_rate_bucket(resolve_client_ip(request))}"
        bucket, limit = "emoji", _EMOJI_RATE_LIMIT
    else:
        identity = _resolve_rate_limit_identity(request, config.jwt_secret.get_secret_value())
        bucket, limit = "global", _GLOBAL_RATE_LIMIT
    redis_key = f"{REDIS_KEY_PREFIX}ratelimit:{bucket}:{identity}"

    try:
        await _enforce(
            redis,
            redis_key,
            limit,
            _GLOBAL_RATE_LIMIT_WINDOW_S,
            bucket,
            f"{bucket} by {identity}",
        )
    except HTTPException:
        raise  # the actual 429, not a Redis failure
    except Exception:  # fail open: Redis being down must not take the API down
        logger.warning("Global rate limiter failed open: Redis unavailable")
