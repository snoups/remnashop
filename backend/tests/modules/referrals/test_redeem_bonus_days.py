from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.models.subscription import Subscription
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PlanType, PurchaseType, SubscriptionStatus
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
from app.modules.referrals.dto import RedeemBonusDaysDto
from app.modules.referrals.usecases.redeem_bonus_days import RedeemBonusDaysUseCase
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot, snapshot_from_plan


@pytest.fixture
def redeem(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    plan_repository: PlanRepository,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    idempotency_repository: PurchaseIdempotencyRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> RedeemBonusDaysUseCase:
    return RedeemBonusDaysUseCase(
        user_repository,
        subscription_repository,
        plan_repository,
        purchase_subscription_use_case,
        idempotency_repository,
        uow,
        event_publisher,
    )


async def _plan(plan_repository: PlanRepository) -> PlanDto:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="bonus-days",
            name="bonus-days",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    return await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))


async def _user_with_days(user_repository: UserRepository, telegram_id: int, days: int) -> UserDto:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=telegram_id))
    await user_repository.credit_bonus_days(user.id, days)
    refreshed = await user_repository.get_by_id(user.id)
    assert refreshed is not None
    return refreshed


async def _paid_subscription(
    purchase: PurchaseSubscriptionUseCase, plan: PlanDto, user: UserDto
) -> SubscriptionDto:
    return await purchase(
        user,
        PurchaseSubscriptionDto(
            user_id=user.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )


async def _set_status(
    subscription_repository: SubscriptionRepository,
    subscription_id: int,
    status: SubscriptionStatus,
) -> None:
    await subscription_repository.session.execute(
        update(Subscription).where(Subscription.id == subscription_id).values(status=status)
    )


async def _bonus_days(user_repository: UserRepository, user_id: int) -> int:
    user = await user_repository.get_by_id(user_id)
    assert user is not None
    return user.bonus_days


async def test_redeem_extends_the_subscription_and_debits_the_balance(
    redeem: RedeemBonusDaysUseCase,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
) -> None:
    plan = await _plan(plan_repository)
    user = await _user_with_days(user_repository, 940_001, 10)
    subscription = await _paid_subscription(purchase_subscription_use_case, plan, user)

    result = await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=4))

    assert result.subscription_id == subscription.id
    # the panel keeps milliseconds
    expected = subscription.expire_at + timedelta(days=4)
    assert abs(result.expire_at - expected) < timedelta(milliseconds=1)
    assert result.bonus_days == 6
    assert await _bonus_days(user_repository, user.id) == 6


async def test_redeem_reactivates_an_expired_subscription(
    redeem: RedeemBonusDaysUseCase,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    plan = await _plan(plan_repository)
    user = await _user_with_days(user_repository, 940_002, 5)
    subscription = await _paid_subscription(purchase_subscription_use_case, plan, user)
    await _set_status(subscription_repository, subscription.id, SubscriptionStatus.EXPIRED)

    result = await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=5))

    assert result.expire_at > datetime_now()
    renewed = await subscription_repository.get_by_id(subscription.id)
    assert renewed.status is SubscriptionStatus.ACTIVE


@pytest.mark.parametrize(
    ("is_trial", "status", "code"),
    [
        (True, SubscriptionStatus.ACTIVE, ErrorCode.BONUS_DAYS_TRIAL_SUBSCRIPTION),
        (False, SubscriptionStatus.DISABLED, ErrorCode.BONUS_DAYS_SUBSCRIPTION_DISABLED),
        (False, SubscriptionStatus.DELETED, ErrorCode.SUBSCRIPTION_DELETED),
    ],
)
async def test_redeem_refuses_an_ineligible_subscription(
    redeem: RedeemBonusDaysUseCase,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    is_trial: bool,
    status: SubscriptionStatus,
    code: ErrorCode,
) -> None:
    user = await _user_with_days(user_repository, 940_003, 5)
    subscription = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=940_003,
            status=status,
            traffic_limit=0,
            device_limit=0,
            expire_at=datetime_now(),
            url="https://example.test/sub",
            plan_snapshot=make_plan_snapshot(plan_id=1, price_paid=Decimal("100")),
            is_trial=is_trial,
        )
    )

    with pytest.raises(ValidationError) as error:
        await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=1))

    assert error.value.code is code
    assert await _bonus_days(user_repository, user.id) == 5


async def test_redeem_refuses_someone_elses_subscription(
    redeem: RedeemBonusDaysUseCase,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    owner = await _user_with_days(user_repository, 940_004, 0)
    user = await _user_with_days(user_repository, 940_005, 5)
    subscription = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=owner.id,
            remnawave_user_id=940_004,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=0,
            device_limit=0,
            expire_at=datetime_now(),
            url="https://example.test/sub",
            plan_snapshot=make_plan_snapshot(plan_id=1, price_paid=Decimal("100")),
        )
    )

    with pytest.raises(ValidationError) as error:
        await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=1))

    assert error.value.code is ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED


async def test_redeem_refuses_more_than_the_balance(
    redeem: RedeemBonusDaysUseCase,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
) -> None:
    plan = await _plan(plan_repository)
    user = await _user_with_days(user_repository, 940_006, 3)
    subscription = await _paid_subscription(purchase_subscription_use_case, plan, user)

    with pytest.raises(ValidationError) as error:
        await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=4))

    assert error.value.code is ErrorCode.BONUS_DAYS_INSUFFICIENT
    assert await _bonus_days(user_repository, user.id) == 3


async def test_redeem_returns_the_days_when_the_renewal_fails(
    redeem: RedeemBonusDaysUseCase,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # committed: the failing renewal's rollback must not take the setup with it
    async with uow:
        plan = await _plan(plan_repository)
        user = await _user_with_days(user_repository, 940_007, 8)
    subscription = await _paid_subscription(purchase_subscription_use_case, plan, user)

    async def _failing_execute(actor: object, data: PurchaseSubscriptionDto) -> SubscriptionDto:
        raise RuntimeError("panel unavailable")

    monkeypatch.setattr(purchase_subscription_use_case, "_execute", _failing_execute)

    with pytest.raises(RuntimeError):
        await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=5))

    assert await _bonus_days(user_repository, user.id) == 8


async def test_redeem_keeps_the_debit_when_the_panel_already_extended(
    redeem: RedeemBonusDaysUseCase,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with uow:
        plan = await _plan(plan_repository)
        user = await _user_with_days(user_repository, 940_008, 8)
    subscription = await _paid_subscription(purchase_subscription_use_case, plan, user)

    # the panel write lands, then the local step fails once
    lifecycle = purchase_subscription_use_case._renew._lifecycle_service
    real_renew = lifecycle.renew
    failures = [RuntimeError("commit lost")]

    async def _renew_failing_once(subscription_id: int, expire_at: object) -> SubscriptionDto:
        if failures:
            raise failures.pop()
        return await real_renew(subscription_id, expire_at)

    monkeypatch.setattr(lifecycle, "renew", _renew_failing_once)

    result = await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=5))

    expected = subscription.expire_at + timedelta(days=5)
    assert abs(result.expire_at - expected) < timedelta(milliseconds=1)
    assert await _bonus_days(user_repository, user.id) == 3


async def test_redeem_records_the_renewal_as_the_customer(
    redeem: RedeemBonusDaysUseCase,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
) -> None:
    plan = await _plan(plan_repository)
    user = await _user_with_days(user_repository, 940_009, 3)
    subscription = await _paid_subscription(purchase_subscription_use_case, plan, user)

    await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=2))

    renewed = (
        await user_repository.session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "SubscriptionRenewedEvent"
            )
        )
    ).one()
    assert renewed.payload["user"]["id"] == user.id


async def test_redeem_reports_insufficient_when_the_balance_moved_meanwhile(
    redeem: RedeemBonusDaysUseCase,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
) -> None:
    plan = await _plan(plan_repository)
    stale = await _user_with_days(user_repository, 940_010, 10)
    subscription = await _paid_subscription(purchase_subscription_use_case, plan, stale)
    # a concurrent redemption spent most of it after the actor was loaded
    await user_repository.credit_bonus_days(stale.id, -8)

    with pytest.raises(ValidationError) as error:
        await redeem(stale, RedeemBonusDaysDto(subscription_id=subscription.id, days=5))

    assert error.value.code is ErrorCode.BONUS_DAYS_INSUFFICIENT
    assert await _bonus_days(user_repository, stale.id) == 2


async def test_redeem_refuses_a_plan_that_disallows_bonus_days(
    redeem: RedeemBonusDaysUseCase,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
) -> None:
    plan = await _plan(plan_repository)
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, allow_bonus_days=False))
    user = await _user_with_days(user_repository, 940_011, 5)
    subscription = await _paid_subscription(purchase_subscription_use_case, plan, user)

    with pytest.raises(ValidationError) as error:
        await redeem(user, RedeemBonusDaysDto(subscription_id=subscription.id, days=2))

    assert error.value.code is ErrorCode.BONUS_DAYS_PLAN_NOT_ALLOWED
    assert await _bonus_days(user_repository, user.id) == 5
