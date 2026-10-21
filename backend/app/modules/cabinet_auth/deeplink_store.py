import hashlib
import secrets
from typing import Final, Optional, Union

from pydantic import TypeAdapter
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TTL_5M
from app.modules.cabinet_auth.dto import BotSignInGrantDto, InviteCodesDto, StartTicketDto

_TOKEN_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:webauth:token:"
_SIGNIN_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:webauth:signin:"
_TICKET_ADAPTER: Final[TypeAdapter[StartTicketDto]] = TypeAdapter(StartTicketDto)
_GRANT_ADAPTER: Final[TypeAdapter[BotSignInGrantDto]] = TypeAdapter(BotSignInGrantDto)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _start_ticket(raw: Optional[Union[bytes, str]]) -> Optional[StartTicketDto]:
    return None if raw is None else _TICKET_ADAPTER.validate_json(raw)


class DeeplinkStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def create(self, codes: InviteCodesDto, link_user_id: Optional[int] = None) -> str:
        token = secrets.token_urlsafe(32)
        ticket = StartTicketDto(codes=codes, link_user_id=link_user_id)
        await self._redis.set(
            f"{_TOKEN_PREFIX}{_hash(token)}", _TICKET_ADAPTER.dump_json(ticket), ex=TTL_5M
        )
        return token

    async def peek(self, token: str) -> Optional[StartTicketDto]:
        return _start_ticket(await self._redis.get(f"{_TOKEN_PREFIX}{_hash(token)}"))

    async def take_start(self, token: str) -> Optional[StartTicketDto]:
        # getdel: one start link mints at most one sign-in token
        return _start_ticket(await self._redis.getdel(f"{_TOKEN_PREFIX}{_hash(token)}"))

    async def issue_signin(self, grant: BotSignInGrantDto) -> str:
        token = secrets.token_urlsafe(32)
        await self._redis.set(
            f"{_SIGNIN_PREFIX}{_hash(token)}", _GRANT_ADAPTER.dump_json(grant), ex=TTL_5M
        )
        return token

    async def take_signin(self, token: str) -> Optional[BotSignInGrantDto]:
        raw = await self._redis.getdel(f"{_SIGNIN_PREFIX}{_hash(token)}")
        return None if raw is None else _GRANT_ADAPTER.validate_json(raw)
