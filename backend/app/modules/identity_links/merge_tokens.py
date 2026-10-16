import hashlib
import json
import secrets
from dataclasses import asdict
from typing import Optional

from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TTL_10M
from app.modules.cabinet_auth import TelegramProfileDto
from app.modules.identity_links.dto import IdentityClaimDto, IdentityKind, MergeTicketDto
from app.modules.oauth import OAuthProfile


def _key(token: str) -> str:
    return f"{REDIS_KEY_PREFIX}identity:merge:{hashlib.sha256(token.encode()).hexdigest()}"


class MergeTokenStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def issue(self, user_id: int, other_user_id: int, claim: IdentityClaimDto) -> str:
        token = secrets.token_urlsafe(32)
        record = {"user_id": user_id, "other_user_id": other_user_id, "claim": asdict(claim)}
        await self._redis.set(_key(token), json.dumps(record), ex=TTL_10M)
        return token

    async def take(self, token: str) -> Optional[MergeTicketDto]:
        # getdel: one token, at most one merge
        raw = await self._redis.getdel(_key(token))
        if raw is None:
            return None
        record = json.loads(raw)
        claim = record["claim"]
        return MergeTicketDto(
            user_id=record["user_id"],
            other_user_id=record["other_user_id"],
            claim=IdentityClaimDto(
                kind=IdentityKind(claim["kind"]),
                telegram=TelegramProfileDto(**claim["telegram"]) if claim["telegram"] else None,
                email=claim["email"],
                oauth=OAuthProfile(**claim["oauth"]) if claim["oauth"] else None,
            ),
        )
