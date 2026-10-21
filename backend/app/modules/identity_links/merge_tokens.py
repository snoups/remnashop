import hashlib
import secrets
from typing import Final, Optional

from pydantic import TypeAdapter
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TTL_10M
from app.modules.identity_links.dto import IdentityClaimDto, MergeTicketDto

_TICKET_ADAPTER: Final[TypeAdapter[MergeTicketDto]] = TypeAdapter(MergeTicketDto)


def _key(token: str) -> str:
    return f"{REDIS_KEY_PREFIX}identity:merge:{hashlib.sha256(token.encode()).hexdigest()}"


class MergeTokenStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def issue(self, user_id: int, other_user_id: int, claim: IdentityClaimDto) -> str:
        token = secrets.token_urlsafe(32)
        ticket = MergeTicketDto(user_id=user_id, other_user_id=other_user_id, claim=claim)
        await self._redis.set(_key(token), _TICKET_ADAPTER.dump_json(ticket), ex=TTL_10M)
        return token

    async def take(self, token: str) -> Optional[MergeTicketDto]:
        # getdel: one token, at most one merge
        raw = await self._redis.getdel(_key(token))
        return None if raw is None else _TICKET_ADAPTER.validate_json(raw)
