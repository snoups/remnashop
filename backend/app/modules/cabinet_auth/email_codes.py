import hashlib
import hmac
import secrets
from dataclasses import dataclass, replace
from typing import ClassVar, Final, Optional

from pydantic import TypeAdapter
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TIME_1D, TIME_1H, TIME_1M, TTL_10M
from app.core.enums import Locale
from app.core.utils.email import canonical_email, normalize_email
from app.core.utils.rate_counter import hit_counter
from app.modules.cabinet_auth.dto import EmailCodeGrantDto, InviteCodesDto

_MAX_ATTEMPTS: Final[int] = 5
_FAIL_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:email_code_fail:"
_DAILY_FAIL_BUDGET: Final[int] = 20
_LIMIT_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:email_code_limit:"
_PER_HOUR: Final[int] = 10


@dataclass(frozen=True, kw_only=True)
class _EmailCodeRecord:
    code_hash: str
    attempts: int
    email: str
    referral_code: Optional[str]
    ad_link_code: Optional[str]
    locale: Locale


_RECORD_ADAPTER: Final[TypeAdapter[_EmailCodeRecord]] = TypeAdapter(_EmailCodeRecord)


class EmailCodeExpired(Exception):  # noqa: N818
    pass


class EmailCodeAttemptsExhausted(Exception):  # noqa: N818
    pass


def email_key(email: str) -> str:
    return hashlib.sha256(canonical_email(email).encode()).hexdigest()


def _hash_code(email_hash: str, code: str) -> str:
    return hashlib.sha256(f"{email_hash}:{code}".encode()).hexdigest()


async def fail_budget_exhausted(redis: Redis, digest: str) -> bool:
    return int(await redis.get(f"{_FAIL_PREFIX}{digest}") or 0) >= _DAILY_FAIL_BUDGET


async def record_failure(redis: Redis, digest: str) -> None:
    await hit_counter(redis, f"{_FAIL_PREFIX}{digest}", TIME_1D)


async def send_limit_hit(redis: Redis, digest: str) -> bool:
    # shared by login and link: one budget per mailbox, whatever the flow
    if await hit_counter(redis, f"{_LIMIT_PREFIX}min:{digest}", TIME_1M) > 1:
        return True
    return await hit_counter(redis, f"{_LIMIT_PREFIX}hour:{digest}", TIME_1H) > _PER_HOUR


class EmailCodeStore:
    key_prefix: ClassVar[str] = f"{REDIS_KEY_PREFIX}cabinet:email_code:"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def issue(self, email: str, codes: InviteCodesDto, locale: Locale) -> str:
        email_hash = email_key(email)
        code = f"{secrets.randbelow(1_000_000):06d}"
        record = _EmailCodeRecord(
            code_hash=_hash_code(email_hash, code),
            attempts=0,
            email=normalize_email(email),
            referral_code=codes.referral_code,
            ad_link_code=codes.ad_link_code,
            locale=locale,
        )
        await self._redis.set(
            f"{self.key_prefix}{email_hash}", _RECORD_ADAPTER.dump_json(record), ex=TTL_10M
        )
        return code

    async def verify(self, email: str, code: str) -> Optional[EmailCodeGrantDto]:
        email_hash = email_key(email)
        key = f"{self.key_prefix}{email_hash}"
        raw = await self._redis.get(key)
        if raw is None:
            raise EmailCodeExpired
        record = _RECORD_ADAPTER.validate_json(raw)
        if record.email == normalize_email(email) and hmac.compare_digest(
            record.code_hash, _hash_code(email_hash, code)
        ):
            # getdel: two parallel correct submissions must not both sign in
            if await self._redis.getdel(key) is None:
                raise EmailCodeExpired
            return EmailCodeGrantDto(
                codes=InviteCodesDto(
                    referral_code=record.referral_code, ad_link_code=record.ad_link_code
                ),
                locale=record.locale,
            )
        record = replace(record, attempts=record.attempts + 1)
        if record.attempts >= _MAX_ATTEMPTS:
            await self._redis.delete(key)
            raise EmailCodeAttemptsExhausted
        # xx: never resurrect a key a parallel request already consumed or burned. A stale
        # payload can still overwrite a freshly issued code; a strict fix needs Lua/WATCH
        await self._redis.set(key, _RECORD_ADAPTER.dump_json(record), keepttl=True, xx=True)
        return None
