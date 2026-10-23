import asyncio

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
    assert len(keys) == 2 and all([await redis.ttl(key) > 0 for key in keys])


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
    keys = [key async for key in redis.scan_iter("*cabinet:email_code:*")]
    assert all(key.endswith(":attempts") for key in keys)


async def test_parallel_wrong_guesses_get_five_attempts_in_total(store: EmailCodeStore) -> None:
    code = await store.issue("a@b.c", InviteCodesDto(), Locale.EN)
    wrong = [f"{n:06d}" for n in range(30) if f"{n:06d}" != code][:20]

    results = await asyncio.gather(
        *(store.verify("a@b.c", guess) for guess in wrong), return_exceptions=True
    )

    evaluated = [result for result in results if result is None]
    assert len(evaluated) == 4  # the fifth wrong guess burns the code
    assert all(
        isinstance(result, (EmailCodeAttemptsExhausted, EmailCodeExpired))
        for result in results
        if result is not None
    )
    with pytest.raises(EmailCodeExpired):
        await store.verify("a@b.c", code)


async def test_code_is_bound_to_the_address_it_was_issued_for(store: EmailCodeStore) -> None:
    code = await store.issue("ivan+x@mail.ru", InviteCodesDto(), Locale.EN)
    assert await store.verify("ivan@mail.ru", code) is None
    assert await store.verify("ivan+x@mail.ru", code) is not None
