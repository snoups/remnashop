import hashlib
import json
import secrets
from dataclasses import asdict
from typing import Final, Optional, Union

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TTL_5M
from app.modules.cabinet_auth.dto import BotSignInGrantDto, InviteCodesDto, TelegramProfileDto

_TOKEN_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:webauth:token:"
_SIGNIN_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:webauth:signin:"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _codes(record: dict[str, object]) -> InviteCodesDto:
    codes = record["codes"]
    assert isinstance(codes, dict)
    return InviteCodesDto(**codes)


def _start_codes(raw: Optional[Union[bytes, str]]) -> Optional[InviteCodesDto]:
    return None if raw is None else _codes(json.loads(raw))


class DeeplinkStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def create(self, codes: InviteCodesDto) -> str:
        token = secrets.token_urlsafe(32)
        record = {"codes": asdict(codes)}
        await self._redis.set(f"{_TOKEN_PREFIX}{_hash(token)}", json.dumps(record), ex=TTL_5M)
        return token

    async def peek(self, token: str) -> Optional[InviteCodesDto]:
        return _start_codes(await self._redis.get(f"{_TOKEN_PREFIX}{_hash(token)}"))

    async def take_start(self, token: str) -> Optional[InviteCodesDto]:
        # getdel: one start link mints at most one sign-in token
        return _start_codes(await self._redis.getdel(f"{_TOKEN_PREFIX}{_hash(token)}"))

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
