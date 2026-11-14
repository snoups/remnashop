from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import pytest
from remnapy import RemnawaveSDK
from remnapy.enums import TrafficLimitStrategy

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PlanType, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.domain import calculate_proration_credit
from app.modules.subscriptions.dto import (
    PurchaseSubscriptionDto,
    SubscriptionDto,
    UpdateSubscriptionDto,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore
from tests.modules.subscriptions.factories import make_eligibility, snapshot_from_plan


async def _plan(plan_repository: PlanRepository, code: str) -> PlanDto:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code=code, name=code, type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[
                SetPlanDurationDto(days=0, order_index=0, base_price=Decimal("5000")),
                SetPlanDurationDto(days=30, order_index=1, base_price=Decimal("500")),
            ],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    return await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))


def _use_case(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> PurchaseSubscriptionUseCase:
    session = subscription_repository.session
    return PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(session),
        idempotency_repository,
        UserRepository(session),
        AppConfig.get(),
    )


async def _buy(
    use_case: PurchaseSubscriptionUseCase,
    buyer: UserDto,
    plan: PlanDto,
    *,
    days: int,
    paid: str,
    purchase_type: PurchaseType = PurchaseType.NEW,
    target_subscription_id: Optional[int] = None,
) -> SubscriptionDto:
    return await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal(paid), currency=Currency.RUB, duration_days=days
            ),
            duration_days=days,
            price_paid=Decimal(paid),
            base_price=Decimal(paid),
            currency=Currency.RUB,
            purchase_type=purchase_type,
            target_subscription_id=target_subscription_id,
        ),
    )


def _panel_expiry(store: FakeUserStore, subscription: SubscriptionDto) -> datetime:
    return datetime.fromisoformat(store[subscription.remnawave_user_id]["expireAt"])


async def test_new_purchase_unlimited_sets_2099_on_panel_and_row(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="forever", telegram_id=91001))
    plan = await _plan(plan_repository, "forever-new")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )

    subscription = await _buy(use_case, buyer, plan, days=0, paid="5000")

    assert subscription.is_unlimited
    assert _panel_expiry(remnawave_store, subscription).year == 2099
    assert subscription.plan_snapshot.effective_credit_days == 0
    assert subscription.plan_snapshot.effective_credit_paid == Decimal("5000")


async def test_trial_upgrade_to_unlimited_sets_2099(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="trial", telegram_id=91002))
    plan = await _plan(plan_repository, "forever-trial-upgrade")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    trial = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("0"), currency=Currency.RUB, duration_days=3, is_trial=True
            ),
            duration_days=3,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    paid = await _buy(use_case, buyer, plan, days=0, paid="5000")

    assert paid.remnawave_user_id == trial.remnawave_user_id
    assert paid.is_unlimited
    assert _panel_expiry(remnawave_store, paid).year == 2099


async def test_renew_refuses_unlimited_target_before_panel(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="renew", telegram_id=91003))
    plan = await _plan(plan_repository, "forever-renew-refused")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    forever = await _buy(use_case, buyer, plan, days=0, paid="5000")
    before = _panel_expiry(remnawave_store, forever)

    with pytest.raises(ValidationError) as error:
        await _buy(
            use_case,
            buyer,
            plan,
            days=30,
            paid="500",
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=forever.id,
        )

    assert error.value.code is ErrorCode.SUBSCRIPTION_UNLIMITED
    assert _panel_expiry(remnawave_store, forever) == before


async def test_renew_finite_with_unlimited_duration(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="upgrade", telegram_id=91004))
    plan = await _plan(plan_repository, "forever-renew-into")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    month = await _buy(use_case, buyer, plan, days=30, paid="500")

    renewed = await _buy(
        use_case,
        buyer,
        plan,
        days=0,
        paid="5000",
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=month.id,
    )

    assert renewed.is_unlimited
    assert _panel_expiry(remnawave_store, renewed).year == 2099
    snapshot = renewed.plan_snapshot
    assert snapshot.unlimited_from == month.expire_at
    assert snapshot.unlimited_from_credit_paid == Decimal("500")
    assert snapshot.unlimited_from_credit_days == 30
    assert snapshot.credit_paid == Decimal("5000")
    assert snapshot.credit_days == 0


async def test_renewable_is_empty_for_unlimited_until_it_turns_finite(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="renewable", telegram_id=91005))
    plan = await _plan(plan_repository, "forever-renewable")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    forever = await _buy(use_case, buyer, plan, days=0, paid="5000")
    eligibility = make_eligibility(subscription_repository.session)

    assert await eligibility.renewable([plan], buyer.id, forever.id) == []

    await subscription_repository.update(
        UpdateSubscriptionDto(
            subscription_id=forever.id, expire_at=datetime(2027, 1, 1, tzinfo=timezone.utc)
        )
    )

    assert [p.id for p in await eligibility.renewable([plan], buyer.id, forever.id)] == [plan.id]


def test_proration_credit_of_unlimited_is_zero() -> None:
    credit = calculate_proration_credit(
        credit_paid=Decimal("5000"),
        credit_days=0,
        expire_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        is_trial=False,
        now=datetime(2026, 11, 14, tzinfo=timezone.utc),
        traffic_limit=0,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        used_traffic_bytes=0,
    )

    assert credit == Decimal("0")


async def test_change_to_unlimited_sets_2099_without_day_credit(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="change", telegram_id=91006))
    month_plan = await _plan(plan_repository, "change-from-month")
    forever_plan = await _plan(plan_repository, "change-to-forever")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    month = await _buy(use_case, buyer, month_plan, days=30, paid="500")

    changed = await _buy(
        use_case,
        buyer,
        forever_plan,
        days=0,
        paid="5000",
        purchase_type=PurchaseType.CHANGE,
        target_subscription_id=month.id,
    )

    assert changed.is_unlimited
    assert _panel_expiry(remnawave_store, changed).year == 2099
    assert changed.plan_snapshot.credit_paid == Decimal("5000")
    assert changed.plan_snapshot.credit_days == 0


async def test_change_unlimited_to_unlimited_accumulates_credit_paid(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # the first purchase's snapshot carries no credit fields, like a migrated one
    buyer = await user_repository.create(CreateUserDto(name="upgrade", telegram_id=91007))
    standard = await _plan(plan_repository, "standard-forever")
    premium = await _plan(plan_repository, "premium-forever")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    forever = await _buy(use_case, buyer, standard, days=0, paid="3000")

    changed = await _buy(
        use_case,
        buyer,
        premium,
        days=0,
        paid="2000",
        purchase_type=PurchaseType.CHANGE,
        target_subscription_id=forever.id,
    )

    assert changed.is_unlimited
    assert changed.plan_snapshot.credit_paid == Decimal("5000")
    assert changed.plan_snapshot.credit_days == 0


async def test_change_unlimited_to_finite_has_zero_credit(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="down", telegram_id=91008))
    forever_plan = await _plan(plan_repository, "down-from-forever")
    month_plan = await _plan(plan_repository, "down-to-month")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    forever = await _buy(use_case, buyer, forever_plan, days=0, paid="5000")

    changed = await _buy(
        use_case,
        buyer,
        month_plan,
        days=30,
        paid="500",
        purchase_type=PurchaseType.CHANGE,
        target_subscription_id=forever.id,
    )

    assert not changed.is_unlimited
    assert changed.expire_at - datetime_now() < timedelta(days=30, minutes=1)
    assert changed.plan_snapshot.credit_days == 30


async def test_a_subscription_made_unlimited_by_hand_changes_to_finite_without_credit(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await user_repository.create(CreateUserDto(name="by-hand", telegram_id=91009))
    month_plan = await _plan(plan_repository, "by-hand-month")
    other_plan = await _plan(plan_repository, "by-hand-other")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    month = await _buy(use_case, buyer, month_plan, days=30, paid="500")
    forever = datetime(2099, 1, 1, tzinfo=timezone.utc)
    await subscription_repository.update(
        UpdateSubscriptionDto(subscription_id=month.id, expire_at=forever)
    )
    remnawave_store[month.remnawave_user_id]["expireAt"] = forever.isoformat()

    changed = await _buy(
        use_case,
        buyer,
        other_plan,
        days=30,
        paid="500",
        purchase_type=PurchaseType.CHANGE,
        target_subscription_id=month.id,
    )

    assert changed.plan_snapshot.credit_days == 30
    assert changed.expire_at - datetime_now() < timedelta(days=30, minutes=1)


async def test_a_free_unlimited_to_unlimited_change_keeps_the_traffic_counter(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # the credit covered it all: back and forth between two plans must not buy a reset
    buyer = await user_repository.create(CreateUserDto(name="loop", telegram_id=91011))
    dear = await _plan(plan_repository, "loop-dear-forever")
    cheap = await _plan(plan_repository, "loop-cheap-forever")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    forever = await _buy(use_case, buyer, dear, days=0, paid="5000")
    remnawave_store[forever.remnawave_user_id]["userTraffic"]["usedTrafficBytes"] = 777

    await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                cheap, price_paid=Decimal("0"), currency=Currency.RUB, duration_days=0
            ),
            duration_days=0,
            price_paid=Decimal("0"),
            base_price=Decimal("4000"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=forever.id,
            reset_traffic=True,
        ),
    )

    assert remnawave_store[forever.remnawave_user_id]["userTraffic"]["usedTrafficBytes"] == 777


async def test_renewing_an_unlimited_turned_finite_does_not_unlock_its_payment(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # unlimited → finite is no credit; a cheap renewal must not turn the
    # unlimited payment into a per-day rate
    buyer = await user_repository.create(CreateUserDto(name="finite", telegram_id=91012))
    plan = await _plan(plan_repository, "forever-made-finite")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    forever = await _buy(use_case, buyer, plan, days=0, paid="5000")
    finite = datetime_now() + timedelta(days=10)
    await subscription_repository.update(
        UpdateSubscriptionDto(subscription_id=forever.id, expire_at=finite)
    )
    remnawave_store[forever.remnawave_user_id]["expireAt"] = finite.isoformat()

    renewed = await _buy(
        use_case,
        buyer,
        plan,
        days=30,
        paid="500",
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=forever.id,
    )

    assert renewed.plan_snapshot.credit_paid == Decimal("500")
    assert renewed.plan_snapshot.credit_days == 30


async def test_a_trial_plan_is_never_issued_unlimited(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # an admin grant and a SUBSCRIPTION promocode both issue through a NEW purchase
    buyer = await user_repository.create(CreateUserDto(name="trial", telegram_id=91013))
    plan = await _plan(plan_repository, "trial-forever")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot_from_plan(
                    plan, currency=Currency.RUB, duration_days=0, is_trial=True
                ),
                duration_days=0,
                price_paid=Decimal("0"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
            ),
        )

    assert error.value.code is ErrorCode.PLAN_TRIAL_UNLIMITED_DURATION
    assert len(remnawave_store) == 0


async def test_a_paid_renewal_is_not_applied_once_the_panel_made_it_unlimited(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # the panel already says 2099, the webhook carrying it hasn't arrived yet
    buyer = await user_repository.create(CreateUserDto(name="ahead", telegram_id=91014))
    plan = await _plan(plan_repository, "panel-ahead")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    month = await _buy(use_case, buyer, plan, days=30, paid="500")
    forever = datetime(2099, 1, 1, tzinfo=timezone.utc)
    remnawave_store[month.remnawave_user_id]["expireAt"] = forever.isoformat()

    with pytest.raises(ValidationError) as error:
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot_from_plan(
                    plan, price_paid=Decimal("500"), currency=Currency.RUB, duration_days=30
                ),
                duration_days=30,
                price_paid=Decimal("500"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=month.id,
                idempotency_key="panel-ahead-renew",
            ),
        )

    assert error.value.code is ErrorCode.SUBSCRIPTION_UNLIMITED
    assert _panel_expiry(remnawave_store, month) == forever


async def test_an_unlimited_change_carries_the_credit_its_order_was_priced_with(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # fulfilment keeps the number checkout took off the price, not a fresh one
    buyer = await user_repository.create(CreateUserDto(name="priced", telegram_id=91015))
    standard = await _plan(plan_repository, "priced-standard")
    premium = await _plan(plan_repository, "priced-premium")
    use_case = _use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    forever = await _buy(use_case, buyer, standard, days=0, paid="3000")

    changed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                premium, price_paid=Decimal("500"), currency=Currency.RUB, duration_days=0
            ),
            duration_days=0,
            price_paid=Decimal("500"),
            base_price=Decimal("3000"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=forever.id,
            change_credit=Decimal("2500"),
        ),
    )

    assert changed.plan_snapshot.credit_paid == Decimal("3000")
