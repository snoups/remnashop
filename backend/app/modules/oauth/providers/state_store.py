import json
import secrets
from dataclasses import asdict, dataclass
from enum import auto
from typing import Final, Optional

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TTL_10M
from app.core.enums import OAuthProvider, UpperStrEnum

_KEY_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}oauth:state:"


class OAuthFlowPurpose(UpperStrEnum):
    LOGIN = auto()
    CONNECT = auto()
    CABINET_LOGIN = auto()


@dataclass(frozen=True, kw_only=True)
class OAuthState:
    provider: OAuthProvider
    purpose: OAuthFlowPurpose
    user_id: Optional[int]
    code_verifier: Optional[str]
    binding_hash: Optional[str] = None
    referral_code: Optional[str] = None
    ad_link_code: Optional[str] = None


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
        payload = json.dumps(asdict(oauth_state))
        await self._redis.set(f"{_KEY_PREFIX}{state}", payload, ex=TTL_10M)
        return state

    async def consume(self, state: str) -> Optional[OAuthState]:
        key = f"{_KEY_PREFIX}{state}"
        payload = await self._redis.getdel(key)
        if payload is None:
            return None

        data = json.loads(payload)
        data["provider"] = OAuthProvider(data["provider"])
        data["purpose"] = OAuthFlowPurpose(data["purpose"])
        return OAuthState(**data)
