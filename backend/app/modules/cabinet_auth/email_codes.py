import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import ClassVar, Final, Optional

from pydantic import TypeAdapter
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, TIME_1D, TIME_1H, TIME_1M, TTL_10M
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.ports import EventPublisher
from app.core.utils.email import canonical_email, normalize_email
from app.core.utils.rate_counter import hit_counter, release_counter
from app.modules.cabinet_auth.dto import EmailCodeGrantDto, InviteCodesDto
from app.modules.cabinet_auth.events import EmailCodeAttemptsExhaustedEvent
from app.modules.settings import CabinetAuthSettingsDto, SettingsRepository
from app.modules.users import UserRepository

_MAX_ATTEMPTS: Final[int] = 5
_FAIL_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:email_code_fail:"
_DAILY_FAIL_BUDGET: Final[int] = 20
_LIMIT_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}cabinet:email_code_limit:"
_PER_HOUR: Final[int] = 10


@dataclass(frozen=True, kw_only=True)
class _EmailCodeRecord:
    code_hash: str
    email: str
    recipient: str
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


async def reserve_attempt(redis: Redis, digest: str) -> bool:
    """Counts a verify attempt against the mailbox's daily budget before it runs,
    so parallel guesses can't all pass; False once the budget is spent.
    An attempt that didn't fail gives its count back with release_attempt."""
    return await hit_counter(redis, f"{_FAIL_PREFIX}{digest}", TIME_1D) <= _DAILY_FAIL_BUDGET


async def release_attempt(redis: Redis, digest: str) -> None:
    await release_counter(redis, f"{_FAIL_PREFIX}{digest}")


async def send_limit_hit(redis: Redis, digest: str) -> bool:
    # shared by login and link: one budget per mailbox, whatever the flow
    if await hit_counter(redis, f"{_LIMIT_PREFIX}min:{digest}", TIME_1M) > 1:
        return True
    return await hit_counter(redis, f"{_LIMIT_PREFIX}hour:{digest}", TIME_1H) > _PER_HOUR


class EmailCodeStore:
    key_prefix: ClassVar[str] = f"{REDIS_KEY_PREFIX}cabinet:email_code:"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def issue(
        self, email: str, codes: InviteCodesDto, locale: Locale, *, recipient: str
    ) -> str:
        email_hash = email_key(email)
        code = f"{secrets.randbelow(1_000_000):06d}"
        record = _EmailCodeRecord(
            code_hash=_hash_code(email_hash, code),
            email=normalize_email(email),
            recipient=normalize_email(recipient),
            referral_code=codes.referral_code,
            ad_link_code=codes.ad_link_code,
            locale=locale,
        )
        key = f"{self.key_prefix}{email_hash}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(key, _RECORD_ADAPTER.dump_json(record), ex=TTL_10M)
            pipe.delete(f"{key}:attempts")
            await pipe.execute()
        return code

    async def verify(self, email: str, code: str) -> Optional[EmailCodeGrantDto]:
        email_hash = email_key(email)
        key = f"{self.key_prefix}{email_hash}"
        raw = await self._redis.get(key)
        if raw is None:
            raise EmailCodeExpired
        record = _RECORD_ADAPTER.validate_json(raw)
        # counted before the comparison: parallel guesses each take their own slot
        attempt = await hit_counter(self._redis, f"{key}:attempts", TTL_10M)
        if attempt > _MAX_ATTEMPTS:
            await self._redis.delete(key)
            raise EmailCodeAttemptsExhausted
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
                recipient=record.recipient,
            )
        if attempt == _MAX_ATTEMPTS:
            await self._redis.delete(key)
            raise EmailCodeAttemptsExhausted
        return None


async def assert_code_reached_owner(
    user_repository: UserRepository, uow: UnitOfWork, email: str, grant: EmailCodeGrantDto
) -> None:
    """A code sent to an alias proves only that mailbox: an account that has taken
    the canonical address since must not be reached through it."""
    async with uow:
        owner = await user_repository.find_by_email(email)
    if owner is not None and normalize_email(owner.email or "") != grant.recipient:
        raise ConflictError("Email already in use", code=ErrorCode.EMAIL_TAKEN)


async def require_email_sign_in(settings_repository: SettingsRepository) -> CabinetAuthSettingsDto:
    cabinet = await settings_repository.get_cabinet_auth_settings()
    email_settings = await settings_repository.get_email_settings()
    if not (cabinet.email_enabled and email_settings.is_configured):
        raise AuthenticationError(
            "Email sign-in is disabled", code=ErrorCode.CABINET_EMAIL_DISABLED
        )
    return cabinet


async def verify_email_code(
    store: EmailCodeStore,
    redis: Redis,
    event_publisher: EventPublisher,
    uow: UnitOfWork,
    email: str,
    code: str,
    client_ip: str,
    *,
    budget: Optional[str] = None,
) -> EmailCodeGrantDto:
    """budget: the failure budget's key, the mailbox's sign-in one unless given."""
    digest = email_key(email)
    budget = budget or digest
    if not await reserve_attempt(redis, budget):
        raise AuthenticationError("The code has expired", code=ErrorCode.EMAIL_CODE_EXPIRED)
    try:
        grant = await store.verify(email, code)
    except EmailCodeExpired:
        await release_attempt(redis, budget)
        raise AuthenticationError(
            "The code has expired", code=ErrorCode.EMAIL_CODE_EXPIRED
        ) from None
    except EmailCodeAttemptsExhausted:
        async with uow:
            await event_publisher.publish(
                EmailCodeAttemptsExhaustedEvent(email_hash=digest, ip_address=client_ip)
            )
        raise AuthenticationError("Wrong code", code=ErrorCode.EMAIL_CODE_INVALID) from None
    if grant is None:
        raise AuthenticationError("Wrong code", code=ErrorCode.EMAIL_CODE_INVALID)
    await release_attempt(redis, budget)
    return grant
