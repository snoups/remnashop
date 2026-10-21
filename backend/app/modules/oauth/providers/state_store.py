import hashlib
import hmac
import secrets
from dataclasses import dataclass
from enum import auto
from typing import Final, Optional

from pydantic import TypeAdapter
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TTL_10M
from app.core.enums import OAuthProvider, UpperStrEnum

_KEY_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}oauth:state:"


def hash_binding(binding: str) -> str:
    return hashlib.sha256(binding.encode()).hexdigest()


def new_binding() -> tuple[str, str]:
    """A secret for the browser's cookie and its hash for the state record."""
    binding = secrets.token_urlsafe(32)
    return binding, hash_binding(binding)


def binding_matches(binding: Optional[str], expected_hash: Optional[str]) -> bool:
    if not binding or expected_hash is None:
        return False
    return hmac.compare_digest(hash_binding(binding), expected_hash)


class OAuthFlowPurpose(UpperStrEnum):
    LOGIN = auto()
    CONNECT = auto()
    CABINET_LOGIN = auto()
    CABINET_CONNECT = auto()


@dataclass(frozen=True, kw_only=True)
class OAuthState:
    provider: OAuthProvider
    purpose: OAuthFlowPurpose
    user_id: Optional[int]
    code_verifier: Optional[str]
    binding_hash: Optional[str] = None
    referral_code: Optional[str] = None
    ad_link_code: Optional[str] = None


_STATE_ADAPTER: Final[TypeAdapter[OAuthState]] = TypeAdapter(OAuthState)


class OAuthStateStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def create(
        self,
        provider: OAuthProvider,
        purpose: OAuthFlowPurpose,
        user_id: Optional[int],
        code_verifier: Optional[str],
        binding_hash: Optional[str] = None,
        referral_code: Optional[str] = None,
        ad_link_code: Optional[str] = None,
    ) -> str:
        state = secrets.token_urlsafe(32)
        oauth_state = OAuthState(
            provider=provider,
            purpose=purpose,
            user_id=user_id,
            code_verifier=code_verifier,
            binding_hash=binding_hash,
            referral_code=referral_code,
            ad_link_code=ad_link_code,
        )
        await self._redis.set(
            f"{_KEY_PREFIX}{state}", _STATE_ADAPTER.dump_json(oauth_state), ex=TTL_10M
        )
        return state

    async def peek_purpose(self, state: str) -> Optional[OAuthFlowPurpose]:
        # read-only: the callback picks its flow first, the flow then consumes the state
        payload = await self._redis.get(f"{_KEY_PREFIX}{state}")
        if payload is None:
            return None
        return _STATE_ADAPTER.validate_json(payload).purpose

    async def consume(self, state: str) -> Optional[OAuthState]:
        key = f"{_KEY_PREFIX}{state}"
        payload = await self._redis.getdel(key)
        if payload is None:
            return None
        return _STATE_ADAPTER.validate_json(payload)
