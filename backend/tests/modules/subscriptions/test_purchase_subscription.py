import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest
from remnapy import RemnawaveSDK
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, Locale, PlanType, PurchaseType, Role, SubscriptionStatus
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.plans.dto import CreatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


async def _create_buyer(user_repository: UserRepository, telegram_id: int) -> UserDto:
    return await user_repository.create(CreateUserDto(name="buyer", telegram_id=telegram_id))


async def _create_plan(plan_repository: PlanRepository, public_code: str = "basic") -> int:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code=public_code,
            name=public_code,
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    return plan.id


async def test_new_purchase_creates_subscription_with_real_remnawave_identity(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 401)
    plan_id = await _create_plan(plan_repository)
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )

    subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    assert subscription.user_id == buyer.id
    assert subscription.traffic_limit == 100
    assert subscription.device_limit == 3
    assert subscription.remnawave_user_id > 0
    assert subscription.url.startswith("https://fake-panel.test/sub/")
    assert subscription.plan_snapshot.plan_id == plan_id
    assert subscription.plan_snapshot.price_paid == Decimal("299.00")
    assert subscription.plan_snapshot.duration_days == 30

    stored = await subscription_repository.list_all()
    assert len(stored) == 1


async def test_new_purchase_forbidden_for_a_different_users_actor(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 402)
    other_actor = await _create_buyer(user_repository, 403)
    plan_id = await _create_plan(plan_repository, "basic2")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            other_actor,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_id=plan_id,
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
            ),
        )


async def test_owner_can_purchase_on_behalf_of_another_user(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 404)
    plan_id = await _create_plan(plan_repository, "basic3")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )

    subscription = await use_case(
        OWNER,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    assert subscription.user_id == buyer.id


async def test_new_purchase_rejects_target_subscription_id(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 405)
    plan_id = await _create_plan(plan_repository, "basic4")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_id=plan_id,
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=1,
            ),
        )


async def test_new_purchase_blocked_at_concurrent_subscription_cap(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 406)
    plan_id = await _create_plan(plan_repository, "basic5")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_id=plan_id,
        duration_days=30,
        price_paid=Decimal("299.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
    )

    for _ in range(3):
        await use_case(buyer, dto)

    with pytest.raises(ValidationError):
        await use_case(buyer, dto)


async def test_renew_extends_expire_at_and_calls_remnawave_extend(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 411)
    plan_id = await _create_plan(plan_repository, "renew1")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    renewed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=original.id,
        ),
    )

    assert renewed.id == original.id
    assert renewed.expire_at == original.expire_at + timedelta(days=30)


async def test_renew_requires_target_subscription_id(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 412)
    plan_id = await _create_plan(plan_repository, "renew2")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_id=plan_id,
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.RENEW,
            ),
        )


async def test_renew_rejects_target_belonging_to_another_user(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 413)
    other_buyer = await _create_buyer(user_repository, 414)
    plan_id = await _create_plan(plan_repository, "renew3")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    other_subscription = await use_case(
        other_buyer,
        PurchaseSubscriptionDto(
            user_id=other_buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_id=plan_id,
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=other_subscription.id,
            ),
        )


async def test_renew_rejects_target_on_a_different_plan(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 415)
    plan_a = await _create_plan(plan_repository, "renew4a")
    plan_b = await _create_plan(plan_repository, "renew4b")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_a,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_id=plan_b,
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=original.id,
            ),
        )


async def test_renew_rejects_a_deleted_target(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 424)
    plan_id = await _create_plan(plan_repository, "renew5")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    await subscription_repository.mark_deleted(original.id)

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_id=plan_id,
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=original.id,
            ),
        )


async def test_change_applies_proration_credit_as_extra_days(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 421)
    old_plan = await _create_plan(plan_repository, "change1old")
    new_plan = await _create_plan(plan_repository, "change1new")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    old_subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=old_plan,
            duration_days=30,
            price_paid=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    # Full 30 days remaining, price_paid=300/30days => daily_rate=10 => full
    # credit=300 => at new plan's daily_rate=10 (300/30) => 30 credit-days.

    changed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=new_plan,
            duration_days=30,
            price_paid=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=old_subscription.id,
        ),
    )

    assert changed.id != old_subscription.id
    assert changed.plan_snapshot.plan_id == new_plan

    old_after = await subscription_repository.list_all()
    old_row = next(s for s in old_after if s.id == old_subscription.id)
    assert old_row.status.value == "DELETED"

    expected_days = 30 + 30  # duration_days + credit_days
    # Two independent floor-truncation points -- the credit calculation's own
    # (old_expire_at - now).days, then this assertion's (expire_at - now).days
    # -- each can shave off a day for the real time elapsed during the test,
    # so the reachable range is up to 2 short of the theoretical maximum.
    assert (changed.expire_at - datetime_now()).days in (
        expected_days - 2,
        expected_days - 1,
        expected_days,
    )


async def test_change_requires_target_subscription_id(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 422)
    plan_id = await _create_plan(plan_repository, "change2")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_id=plan_id,
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.CHANGE,
            ),
        )


async def test_change_from_trial_gives_no_credit(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 423)
    trial_plan = await plan_repository.create(
        CreatePlanDto(
            public_code="trial1",
            name="trial1",
            type=PlanType.BOTH,
            traffic_limit=10,
            device_limit=1,
            is_trial=True,
        )
    )
    new_plan = await _create_plan(plan_repository, "change3new")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    trial_subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=trial_plan.id,
            duration_days=7,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    changed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=new_plan,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=trial_subscription.id,
        ),
    )

    # No credit -- expire_at is just now + 30 days, no bonus days.
    assert (changed.expire_at - datetime_now()).days in (29, 30)


async def test_acquire_purchase_cap_lock_serializes_concurrent_callers(
    engine: AsyncEngine,
) -> None:
    async with engine.connect() as conn_a, engine.connect() as conn_b:
        session_a = AsyncSession(bind=conn_a, expire_on_commit=False)
        session_b = AsyncSession(bind=conn_b, expire_on_commit=False)
        repo_a = SubscriptionRepository(session_a)
        repo_b = SubscriptionRepository(session_b)

        await repo_a.acquire_purchase_cap_lock(999999)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(repo_b.acquire_purchase_cap_lock(999999), timeout=0.5)
        # wait_for's cancellation aborts the in-flight query, leaving
        # session_b's connection needing an explicit rollback before reuse.
        await session_b.rollback()

        await session_a.rollback()  # pg_advisory_xact_lock releases at transaction end

        await asyncio.wait_for(repo_b.acquire_purchase_cap_lock(999999), timeout=0.5)

        await session_a.close()
        await session_b.close()


async def test_purchase_with_same_idempotency_key_returns_existing_subscription(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 403)
    plan_id = await _create_plan(plan_repository, "idem-test")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_id=plan_id,
        duration_days=30,
        price_paid=Decimal("100.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        idempotency_key="fixed-key-1",
    )

    first = await use_case(buyer, dto)
    second = await use_case(buyer, dto)

    assert first.id == second.id
    assert len(await subscription_repository.get_active_by_user(buyer.id)) == 1


async def test_purchase_failure_after_panel_call_deletes_the_panel_user(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _create_buyer(user_repository, 404)
    plan_id = await _create_plan(plan_repository, "compensate-test")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )

    deleted_ids: list[int] = []
    original_delete = remnawave_sdk.users.delete_user

    async def _tracking_delete(user_id: int) -> None:
        deleted_ids.append(user_id)
        await original_delete(user_id)

    monkeypatch.setattr(remnawave_sdk.users, "delete_user", _tracking_delete)

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(subscription_repository, "create", _boom)

    with pytest.raises(RuntimeError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_id=plan_id,
                duration_days=30,
                price_paid=Decimal("100.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
            ),
        )

    assert len(deleted_ids) == 1


async def test_renew_reactivates_an_expired_subscription(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 405)
    plan_id = await _create_plan(plan_repository, "renew-test")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    purchased = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("100.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    async with uow:
        await SubscriptionLifecycleService(subscription_repository).sync_status(
            purchased.id, SubscriptionStatus.EXPIRED
        )

    renewed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("100.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=purchased.id,
        ),
    )

    assert renewed.status is SubscriptionStatus.ACTIVE


async def test_renew_with_same_idempotency_key_returns_existing_subscription(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    buyer = await _create_buyer(user_repository, 407)
    plan_id = await _create_plan(plan_repository, "idem-renew-test")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    purchased = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_id=plan_id,
            duration_days=30,
            price_paid=Decimal("100.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    renew_dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_id=plan_id,
        duration_days=30,
        price_paid=Decimal("100.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=purchased.id,
        idempotency_key="fixed-renew-key",
    )

    first = await use_case(buyer, renew_dto)
    second = await use_case(buyer, renew_dto)

    assert first.id == second.id == purchased.id
    assert first.expire_at == second.expire_at


async def test_purchase_with_idempotency_key_can_retry_after_a_failed_attempt(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _create_buyer(user_repository, 408)
    plan_id = await _create_plan(plan_repository, "idem-retry-test")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_id=plan_id,
        duration_days=30,
        price_paid=Decimal("100.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        idempotency_key="retry-key-1",
    )

    original_create = subscription_repository.create
    call_count = {"n": 0}

    async def _boom_once(data: CreateSubscriptionDto) -> SubscriptionDto:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated DB failure")
        return await original_create(data)

    monkeypatch.setattr(subscription_repository, "create", _boom_once)

    with pytest.raises(RuntimeError):
        await use_case(buyer, dto)

    subscription = await use_case(buyer, dto)

    assert subscription.user_id == buyer.id


async def test_idempotency_key_is_released_after_a_panel_call_failure(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _create_buyer(user_repository, 409)
    plan_id = await _create_plan(plan_repository, "idem-panel-fail-test")
    use_case = PurchaseSubscriptionUseCase(
        plan_repository,
        subscription_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_id=plan_id,
        duration_days=30,
        price_paid=Decimal("100.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        idempotency_key="panel-fail-key-1",
    )

    original_create_user = remnawave_sdk.users.create_user
    call_count = {"n": 0}

    async def _boom_once(*args: object, **kwargs: object) -> object:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated panel timeout")
        return await original_create_user(*args, **kwargs)

    monkeypatch.setattr(remnawave_sdk.users, "create_user", _boom_once)

    with pytest.raises(RuntimeError):
        await use_case(buyer, dto)

    subscription = await use_case(buyer, dto)

    assert subscription.user_id == buyer.id
