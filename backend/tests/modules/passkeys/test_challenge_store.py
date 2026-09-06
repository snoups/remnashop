from redis.asyncio import Redis

from app.modules.passkeys.challenge_store import PasskeyChallengeStore


async def test_registration_challenge_roundtrips_and_is_consumed_once(redis: Redis) -> None:
    store = PasskeyChallengeStore(redis)
    await store.store_registration_challenge(42, b"\x01\x02\x03")

    challenge = await store.consume_registration_challenge(42)
    assert challenge == b"\x01\x02\x03"

    assert await store.consume_registration_challenge(42) is None


async def test_consume_registration_challenge_returns_none_when_missing(redis: Redis) -> None:
    store = PasskeyChallengeStore(redis)
    assert await store.consume_registration_challenge(999) is None


async def test_authentication_challenge_roundtrips_and_is_consumed_once(redis: Redis) -> None:
    store = PasskeyChallengeStore(redis)
    await store.store_authentication_challenge("abc-b64")

    assert await store.consume_authentication_challenge("abc-b64") is True
    assert await store.consume_authentication_challenge("abc-b64") is False


async def test_consume_authentication_challenge_returns_false_when_missing(redis: Redis) -> None:
    store = PasskeyChallengeStore(redis)
    assert await store.consume_authentication_challenge("nope") is False
