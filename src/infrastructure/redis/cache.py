from functools import wraps
from typing import Any, Awaitable, Callable, Optional, ParamSpec, TypeVar, get_type_hints

from loguru import logger
from pydantic import SecretStr, TypeAdapter
from redis.asyncio import Redis
from redis.typing import ExpiryT

from src.core.constants import TIME_1M
from src.core.utils import json_utils

T = TypeVar("T", bound=Any)
P = ParamSpec("P")


def prepare_for_cache(obj: Any) -> Any:
    if isinstance(obj, SecretStr):
        return obj.get_secret_value()
    elif isinstance(obj, dict):
        return {k: prepare_for_cache(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [prepare_for_cache(v) for v in obj]
    return obj


def redis_cache(
    prefix: Optional[str] = None,
    ttl: ExpiryT = TIME_1M,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        return_type: Any = get_type_hints(func)["return"]
        type_adapter: TypeAdapter[T] = TypeAdapter(return_type)

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            self: Any = args[0]
            redis: Redis = self.redis_client

            # Build cache key
            key_parts = [
                "cache",
                prefix or func.__name__,
                *map(str, args[1:]),
                *map(str, kwargs.values()),
            ]
            key: str = ":".join(key_parts)

            try:
                cached_value: Optional[bytes] = await redis.get(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: '{key}'")
                    parsed = json_utils.decode(cached_value.decode())
                    return type_adapter.validate_python(parsed)

                logger.debug(f"Cache miss: '{key}'. Executing function")
                result: T = await func(*args, **kwargs)

                # Serialize and store result
                safe_result = prepare_for_cache(type_adapter.dump_python(result))
                await redis.setex(key, ttl, json_utils.encode(safe_result))
                logger.debug(f"Result cached: '{key}' (ttl={ttl})")

                return result

            except Exception as exception:
                logger.warning(f"Cache operation failed for key '{key}': {exception}")
                return await func(*args, **kwargs)

        return wrapper

    return decorator
