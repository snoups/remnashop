from typing import Final, Optional

from redis.asyncio import Redis
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from app.core.constants import REDIS_KEY_PREFIX, TTL_5M

_REGISTER_KEY_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}passkeys:register:"
_AUTH_KEY_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}passkeys:auth:"


class PasskeyChallengeStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def store_registration_challenge(self, user_id: int, challenge: bytes) -> None:
        await self._redis.set(
            f"{_REGISTER_KEY_PREFIX}{user_id}", bytes_to_base64url(challenge), ex=TTL_5M
        )

    async def consume_registration_challenge(self, user_id: int) -> Optional[bytes]:
        value = await self._redis.getdel(f"{_REGISTER_KEY_PREFIX}{user_id}")
        return base64url_to_bytes(value) if value is not None else None

    async def store_authentication_challenge(self, challenge_b64: str) -> None:
        await self._redis.set(f"{_AUTH_KEY_PREFIX}{challenge_b64}", "1", ex=TTL_5M)

    async def consume_authentication_challenge(self, challenge_b64: str) -> bool:
        deleted = await self._redis.getdel(f"{_AUTH_KEY_PREFIX}{challenge_b64}")
        return deleted is not None
