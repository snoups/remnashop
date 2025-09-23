from functools import wraps
from typing import Any, Awaitable, Callable, Optional, ParamSpec, TypeVar, get_type_hints

from loguru import logger
from pydantic import TypeAdapter
from redis.asyncio import Redis
from redis.typing import ExpiryT

from src.core.constants import TIME_1M
from src.core.utils import mjson

T = TypeVar("T", bound=Any)
P = ParamSpec("P")


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
                    logger.debug(f"Cache hit for key: {key}")
                    # Decode the bytes and then parse the JSON string
                    return type_adapter.validate_python(mjson.decode(cached_value.decode()))

                logger.debug(f"Cache miss for key: {key}. Executing function")
                result: T = await func(*args, **kwargs)

                # Serialize the result to a JSON string before caching
                cached_result: str = mjson.encode(type_adapter.dump_python(result))
                await redis.setex(key, ttl, cached_result)

                return result

            except Exception as exception:
                logger.error(f"Cache operation failed for key '{key}': {exception}")
                # Fallback to executing the function without caching
                return await func(*args, **kwargs)

        return wrapper

    return decorator
