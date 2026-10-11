import hashlib
import hmac
import json
import secrets
from dataclasses import asdict
from typing import Final, Optional

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TTL_5M
from app.modules.cabinet_auth.dto import (
    DeeplinkPendingDto,
    DeeplinkResult,
    DeeplinkStatus,
    InviteCodesDto,
    TelegramProfileDto,
)

_TOKEN_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:webauth:token:"
_AGENT_MAX: Final[int] = 120
_BINDING_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:webauth:binding:"

# KEYS[1] token record; ARGV[1] profile json, kept as an opaque string (cjson would round
# 52-bit+ numbers). Keeps the TTL; 1 only on PENDING -> CONFIRMED
_CONFIRM_SCRIPT: Final[str] = """
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local record = cjson.decode(raw)
if record['status'] ~= 'PENDING' then return 0 end
record['status'] = 'CONFIRMED'
record['profile'] = ARGV[1]
redis.call('SET', KEYS[1], cjson.encode(record), 'KEEPTTL')
return 1
"""


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _codes(record: dict[str, object]) -> InviteCodesDto:
    codes = record["codes"]
    assert isinstance(codes, dict)
    return InviteCodesDto(**codes)


class DeeplinkStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._confirm = redis.register_script(_CONFIRM_SCRIPT)

    async def create(
        self, codes: InviteCodesDto, client_ip: str, user_agent: Optional[str]
    ) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        binding = secrets.token_urlsafe(32)
        token_hash, binding_hash = _hash(token), _hash(binding)
        record = {
            "binding": binding_hash,
            "status": DeeplinkStatus.PENDING.name,
            "codes": asdict(codes),
            "profile": None,
            "client_ip": client_ip,
            "user_agent": (user_agent or "")[:_AGENT_MAX],
        }
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(f"{_TOKEN_PREFIX}{token_hash}", json.dumps(record), ex=TTL_5M)
            pipe.set(f"{_BINDING_PREFIX}{binding_hash}", token_hash, ex=TTL_5M)
            await pipe.execute()
        return token, binding

    async def peek(self, token: str) -> Optional[DeeplinkPendingDto]:
        raw = await self._redis.get(f"{_TOKEN_PREFIX}{_hash(token)}")
        if raw is None:
            return None
        record = json.loads(raw)
        if record["status"] != DeeplinkStatus.PENDING.name:
            return None
        return DeeplinkPendingDto(
            codes=_codes(record),
            client_ip=record["client_ip"],
            user_agent=record["user_agent"],
        )

    async def confirm(self, token: str, profile: TelegramProfileDto) -> bool:
        result = await self._confirm(
            keys=[f"{_TOKEN_PREFIX}{_hash(token)}"], args=[json.dumps(asdict(profile))]
        )
        return bool(result)

    async def take(self, binding: str) -> DeeplinkResult:
        binding_hash = _hash(binding)
        token_hash = await self._redis.get(f"{_BINDING_PREFIX}{binding_hash}")
        if token_hash is None:
            return DeeplinkResult(status=DeeplinkStatus.EXPIRED)
        token_key = f"{_TOKEN_PREFIX}{token_hash}"
        raw = await self._redis.get(token_key)
        if raw is None:
            return DeeplinkResult(status=DeeplinkStatus.EXPIRED)
        record = json.loads(raw)
        if not hmac.compare_digest(record["binding"], binding_hash):
            return DeeplinkResult(status=DeeplinkStatus.EXPIRED)
        if record["status"] == DeeplinkStatus.PENDING.name:
            return DeeplinkResult(status=DeeplinkStatus.PENDING)
        # getdel: parallel polls must not both sign in
        if await self._redis.getdel(token_key) is None:
            return DeeplinkResult(status=DeeplinkStatus.EXPIRED)
        await self._redis.delete(f"{_BINDING_PREFIX}{binding_hash}")
        return DeeplinkResult(
            status=DeeplinkStatus.CONFIRMED,
            profile=TelegramProfileDto(**json.loads(record["profile"])),
            codes=_codes(record),
        )
