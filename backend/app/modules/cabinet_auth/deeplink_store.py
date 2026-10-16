import hashlib
import json
import secrets
from dataclasses import asdict
from typing import Final, Optional

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TTL_5M
from app.modules.cabinet_auth.dto import (
    BotSignInGrantDto,
    DeeplinkPendingDto,
    InviteCodesDto,
    TelegramProfileDto,
)

_TOKEN_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:webauth:token:"
_AGENT_MAX: Final[int] = 120
_SIGNIN_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:webauth:signin:"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _codes(record: dict[str, object]) -> InviteCodesDto:
    codes = record["codes"]
    assert isinstance(codes, dict)
    return InviteCodesDto(**codes)


class DeeplinkStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def create(self, codes: InviteCodesDto, client_ip: str, user_agent: Optional[str]) -> str:
        token = secrets.token_urlsafe(32)
        record = {
            "codes": asdict(codes),
            "client_ip": client_ip,
            "user_agent": (user_agent or "")[:_AGENT_MAX],
        }
        await self._redis.set(f"{_TOKEN_PREFIX}{_hash(token)}", json.dumps(record), ex=TTL_5M)
        return token

    async def peek(self, token: str) -> Optional[DeeplinkPendingDto]:
        raw = await self._redis.get(f"{_TOKEN_PREFIX}{_hash(token)}")
        if raw is None:
            return None
        record = json.loads(raw)
        return DeeplinkPendingDto(
            codes=_codes(record),
            client_ip=record["client_ip"],
            user_agent=record["user_agent"],
        )

    async def take_start(self, token: str) -> Optional[DeeplinkPendingDto]:
        # getdel: one start link mints at most one sign-in token
        raw = await self._redis.getdel(f"{_TOKEN_PREFIX}{_hash(token)}")
        if raw is None:
            return None
        record = json.loads(raw)
        return DeeplinkPendingDto(
            codes=_codes(record),
            client_ip=record["client_ip"],
            user_agent=record["user_agent"],
        )

    async def issue_signin(self, grant: BotSignInGrantDto) -> str:
        token = secrets.token_urlsafe(32)
        record = {"profile": asdict(grant.profile), "codes": asdict(grant.codes)}
        await self._redis.set(f"{_SIGNIN_PREFIX}{_hash(token)}", json.dumps(record), ex=TTL_5M)
        return token

    async def take_signin(self, token: str) -> Optional[BotSignInGrantDto]:
        raw = await self._redis.getdel(f"{_SIGNIN_PREFIX}{_hash(token)}")
        if raw is None:
            return None
        record = json.loads(raw)
        return BotSignInGrantDto(
            profile=TelegramProfileDto(**record["profile"]), codes=_codes(record)
        )
