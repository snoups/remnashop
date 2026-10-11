import pytest
from redis.asyncio import Redis

from app.core.enums import Locale
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.email_codes import (
    EmailCodeAttemptsExhausted,
    EmailCodeExpired,
    EmailCodeStore,
)


@pytest.fixture
def store(redis: Redis) -> EmailCodeStore:
    return EmailCodeStore(redis)


async def test_code_roundtrip_keeps_invite_codes(store: EmailCodeStore) -> None:
    code = await store.issue("Ann@Mail.ru", InviteCodesDto(referral_code="abc"), Locale.RU)
    assert len(code) == 6 and code.isdigit()
    grant = await store.verify(" ann@mail.ru", code)
    assert grant is not None and grant.codes.referral_code == "abc" and grant.locale is Locale.RU
    with pytest.raises(EmailCodeExpired):
        await store.verify("ann@mail.ru", code)


async def test_new_request_replaces_code(store: EmailCodeStore) -> None:
    first = await store.issue("a@b.c", InviteCodesDto(), Locale.EN)
    second = await store.issue("a@b.c", InviteCodesDto(), Locale.EN)
    if first != second:
        assert await store.verify("a@b.c", first) is None
    assert await store.verify("a@b.c", second) is not None


async def test_five_wrong_attempts_burn_the_code(store: EmailCodeStore) -> None:
    code = await store.issue("a@b.c", InviteCodesDto(), Locale.EN)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(4):
        assert await store.verify("a@b.c", wrong) is None
    with pytest.raises(EmailCodeAttemptsExhausted):
        await store.verify("a@b.c", wrong)
    with pytest.raises(EmailCodeExpired):
        await store.verify("a@b.c", code)


async def test_wrong_attempt_keeps_ttl(store: EmailCodeStore, redis: Redis) -> None:
    code = await store.issue("a@b.c", InviteCodesDto(), Locale.EN)
    wrong = "000000" if code != "000000" else "111111"
    await store.verify("a@b.c", wrong)
    keys = [key async for key in redis.scan_iter("*cabinet:email_code:*")]
    assert len(keys) == 1 and await redis.ttl(keys[0]) > 0


async def test_wrong_attempt_does_not_resurrect_consumed_code(
    store: EmailCodeStore, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    code = await store.issue("a@b.c", InviteCodesDto(), Locale.EN)
    wrong = "000000" if code != "000000" else "111111"
    real_get = redis.get

    async def get_then_consume(key: str) -> object:
        raw = await real_get(key)
        await redis.delete(key)  # a parallel correct submission lands after our read
        return raw

    monkeypatch.setattr(redis, "get", get_then_consume)
    assert await store.verify("a@b.c", wrong) is None
    assert [key async for key in redis.scan_iter("*cabinet:email_code:*")] == []
