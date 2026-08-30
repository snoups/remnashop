import asyncio

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.models.promocode import Promocode
from app.core.enums import PromocodeAvailability, PromocodeRewardType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.promocodes.dto import CreatePromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository

# Race-window guard for the concurrency test below: 50ms of dead air between
# claim_activation's locking SELECT returning and its follow-up count query
# is far longer than either side's real round-trip, so both sides are
# guaranteed to overlap there regardless of scheduling luck.
_RACE_WINDOW_DELAY_SECONDS: float = 0.05


def _create_dto(code: str = "WELCOME10", **overrides: object) -> CreatePromocodeDto:
    defaults: dict = {"code": code, "reward_type": PromocodeRewardType.DURATION, "reward": 30}
    defaults.update(overrides)
    return CreatePromocodeDto(**defaults)


async def _create_user(user_repository: UserRepository, telegram_id: int) -> int:
    user = await user_repository.create(CreateUserDto(name="buyer", telegram_id=telegram_id))
    return user.id


async def test_create_then_get_by_code_returns_promocode(
    promocode_repository: PromocodeRepository,
) -> None:
    created = await promocode_repository.create(_create_dto())

    found = await promocode_repository.get_by_code("WELCOME10")

    assert found is not None
    assert found.id == created.id
    assert found.is_active is True
    assert found.reward == 30


async def test_get_by_code_unknown_returns_none(promocode_repository: PromocodeRepository) -> None:
    assert await promocode_repository.get_by_code("NOPE") is None


async def test_create_duplicate_code_raises_conflict(
    promocode_repository: PromocodeRepository,
) -> None:
    await promocode_repository.create(_create_dto("DUP"))

    with pytest.raises(ConflictError):
        await promocode_repository.create(_create_dto("DUP"))


async def test_get_by_id_unknown_raises_not_found(
    promocode_repository: PromocodeRepository,
) -> None:
    with pytest.raises(NotFoundError):
        await promocode_repository.get_by_id(999_999)


async def test_list_all_returns_created_promocodes(
    promocode_repository: PromocodeRepository,
) -> None:
    await promocode_repository.create(_create_dto("A"))
    await promocode_repository.create(_create_dto("B"))

    codes = {promo.code for promo in await promocode_repository.list_all()}

    assert codes == {"A", "B"}


async def test_update_partial_leaves_other_fields_untouched(
    promocode_repository: PromocodeRepository,
) -> None:
    created = await promocode_repository.create(_create_dto("PARTIAL", max_activations=5))

    updated = await promocode_repository.update(
        UpdatePromocodeDto(promocode_id=created.id, is_active=False)
    )

    assert updated.is_active is False
    assert updated.max_activations == 5  # untouched


async def test_delete_removes_promocode(promocode_repository: PromocodeRepository) -> None:
    created = await promocode_repository.create(_create_dto("GONE"))

    await promocode_repository.delete(created.id)

    assert await promocode_repository.get_by_code("GONE") is None


async def test_delete_unknown_raises_not_found(promocode_repository: PromocodeRepository) -> None:
    with pytest.raises(NotFoundError):
        await promocode_repository.delete(999_999)


async def test_claim_activation_records_activation(
    promocode_repository: PromocodeRepository, user_repository: UserRepository
) -> None:
    created = await promocode_repository.create(_create_dto("CLAIM"))
    user_id = await _create_user(user_repository, 1001)

    activation = await promocode_repository.claim_activation(
        promocode_id=created.id, user_id=user_id, subscription_id=None
    )

    assert activation.promocode_id == created.id
    assert activation.user_id == user_id


async def test_claim_activation_second_time_by_same_user_raises_when_not_reusable(
    promocode_repository: PromocodeRepository, user_repository: UserRepository
) -> None:
    created = await promocode_repository.create(_create_dto("ONCE", is_reusable=False))
    user_id = await _create_user(user_repository, 1002)
    await promocode_repository.claim_activation(
        promocode_id=created.id, user_id=user_id, subscription_id=None
    )

    with pytest.raises(ValidationError):
        await promocode_repository.claim_activation(
            promocode_id=created.id, user_id=user_id, subscription_id=None
        )


async def test_claim_activation_second_time_by_same_user_allowed_when_reusable(
    promocode_repository: PromocodeRepository, user_repository: UserRepository
) -> None:
    created = await promocode_repository.create(_create_dto("REUSE", is_reusable=True))
    user_id = await _create_user(user_repository, 1003)
    await promocode_repository.claim_activation(
        promocode_id=created.id, user_id=user_id, subscription_id=None
    )

    second = await promocode_repository.claim_activation(
        promocode_id=created.id, user_id=user_id, subscription_id=None
    )
    assert second.user_id == user_id


async def test_claim_activation_raises_once_max_activations_reached(
    promocode_repository: PromocodeRepository, user_repository: UserRepository
) -> None:
    created = await promocode_repository.create(_create_dto("CAPPED", max_activations=1))
    first_user_id = await _create_user(user_repository, 1004)
    second_user_id = await _create_user(user_repository, 1005)
    await promocode_repository.claim_activation(
        promocode_id=created.id, user_id=first_user_id, subscription_id=None
    )

    with pytest.raises(ValidationError):
        await promocode_repository.claim_activation(
            promocode_id=created.id, user_id=second_user_id, subscription_id=None
        )


def _widen_locking_select_race_window(session: AsyncSession) -> None:
    # Pauses right after claim_activation's locking SELECT returns, before
    # its caller issues the follow-up max_activations count query. Without
    # this, whichever of the two sessions happens to dispatch its query a
    # few microseconds sooner reliably finishes its whole claim (and
    # commits) before the other side's count query even runs -- on a local
    # Postgres the round trip is fast enough that the two sides essentially
    # never overlap on their own, silently defeating the race this test
    # exists to catch. With the row lock in place, the losing side's SELECT
    # blocks server-side until the winner commits, so this pause never
    # actually applies to it -- it only ever widens the (buggy) unlocked case.
    original_execute = session.execute

    async def _delayed_execute(statement: object, *args: object, **kwargs: object) -> object:
        result = await original_execute(statement, *args, **kwargs)
        sql = str(statement).lower()
        if "from promocodes" in sql and "count(" not in sql:
            await asyncio.sleep(_RACE_WINDOW_DELAY_SECONDS)
        return result

    session.execute = _delayed_execute  # type: ignore[assignment]


async def test_claim_activation_concurrent_calls_against_cap_only_one_succeeds(
    engine: AsyncEngine,
) -> None:
    # Two independent sessions/connections, not the shared savepoint-bound
    # `session` fixture -- that one is single-connection and can't demonstrate
    # cross-connection row locking. Each session commits for real, so this
    # cleans up after itself in a try/finally instead of relying on rollback.
    session_a = AsyncSession(bind=engine, expire_on_commit=False)
    session_b = AsyncSession(bind=engine, expire_on_commit=False)
    promocode_id = None
    first_user_id = None
    second_user_id = None
    try:
        created = await PromocodeRepository(session_a).create(
            _create_dto("RACE1", max_activations=1)
        )
        promocode_id = created.id
        first_user_id = await _create_user(UserRepository(session_a), 9101)
        second_user_id = await _create_user(UserRepository(session_a), 9102)
        await session_a.commit()

        # Warm both connections' plan cache with the exact query shape
        # claim_activation's locking SELECT issues -- an unwarmed connection's
        # first query is itself slow enough to reproduce the same false-pass
        # the delay above guards against.
        locking_select = select(Promocode).where(Promocode.id == promocode_id)
        await session_a.execute(locking_select)
        await session_b.execute(locking_select)
        _widen_locking_select_race_window(session_a)
        _widen_locking_select_race_window(session_b)

        async def _claim(session: AsyncSession, user_id: int) -> object:
            # Commits/rolls back inside the coroutine (not after gather) --
            # gather runs both concurrently, and the losing session's
            # SELECT ... FOR UPDATE blocks until the winner's transaction
            # ends, so the release has to happen before gather returns.
            repo = PromocodeRepository(session)
            try:
                result = await repo.claim_activation(
                    promocode_id=promocode_id, user_id=user_id, subscription_id=None
                )
            except Exception:
                await session.rollback()
                raise
            await session.commit()
            return result

        results = await asyncio.gather(
            _claim(session_a, first_user_id),
            _claim(session_b, second_user_id),
            return_exceptions=True,
        )

        successes = [result for result in results if not isinstance(result, BaseException)]
        failures = [result for result in results if isinstance(result, BaseException)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], ValidationError)
    finally:
        await session_a.close()
        await session_b.close()
        async with engine.begin() as connection:
            if promocode_id is not None:
                await connection.execute(
                    text("DELETE FROM promocode_activations WHERE promocode_id = :id"),
                    {"id": promocode_id},
                )
                await connection.execute(
                    text("DELETE FROM promocodes WHERE id = :id"), {"id": promocode_id}
                )
            for user_id in (first_user_id, second_user_id):
                if user_id is not None:
                    await connection.execute(
                        text("DELETE FROM users WHERE id = :id"), {"id": user_id}
                    )


async def test_update_allowed_availability(promocode_repository: PromocodeRepository) -> None:
    created = await promocode_repository.create(_create_dto("ALLOWLIST"))

    updated = await promocode_repository.update(
        UpdatePromocodeDto(
            promocode_id=created.id,
            availability=PromocodeAvailability.ALLOWED,
            allowed_user_ids=[7, 8],
        )
    )

    assert updated.availability == PromocodeAvailability.ALLOWED
    assert updated.allowed_user_ids == [7, 8]
