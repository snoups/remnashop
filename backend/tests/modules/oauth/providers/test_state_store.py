from redis.asyncio import Redis

from app.core.enums import OAuthProvider
from app.modules.oauth.providers.state_store import OAuthFlowPurpose, OAuthStateStore


async def test_create_then_consume_roundtrips(redis: Redis) -> None:
    store = OAuthStateStore(redis)

    state = await store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier="verifier-123",
    )

    result = await store.consume(state)
    assert result is not None
    assert result.provider == OAuthProvider.GITHUB
    assert result.purpose == OAuthFlowPurpose.LOGIN
    assert result.user_id is None
    assert result.code_verifier == "verifier-123"


async def test_consume_is_one_time_use(redis: Redis) -> None:
    store = OAuthStateStore(redis)
    state = await store.create(
        provider=OAuthProvider.TELEGRAM,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=7,
        code_verifier=None,
    )

    first = await store.consume(state)
    second = await store.consume(state)

    assert first is not None
    assert second is None


async def test_consume_returns_none_for_unknown_state(redis: Redis) -> None:
    store = OAuthStateStore(redis)
    result = await store.consume("does-not-exist")
    assert result is None
