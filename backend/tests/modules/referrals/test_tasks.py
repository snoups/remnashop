from datetime import timedelta
from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.referral_reward import ReferralReward
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.pricing.repository import PricingRepository
from app.modules.referrals.dto import (
    AssignReferralRewardsDto,
    AttachReferralOnRegistrationDto,
    ReferralSettingsDto,
    UpdateReferralSettingsDto,
)
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases import AttachReferralOnRegistrationUseCase
from app.modules.referrals.usecases.assign_referral_rewards import (
    AssignReferralRewardsUseCase,
    _level_amounts,
)
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot


@pytest.fixture
def assign_rewards(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> AssignReferralRewardsUseCase:
    session = referral_repository.session
    return AssignReferralRewardsUseCase(
        referral_repository,
        TransactionRepository(session),
        user_repository,
        subscription_repository,
        uow,
        event_publisher,
    )


async def _set_status(
    session: AsyncSession, order_id: int, status: TransactionStatus = TransactionStatus.PAID
) -> None:
    await TransactionRepository(session).mark_status_if(
        order_id, status, current=frozenset(TransactionStatus)
    )


async def _paid_order(session: AsyncSession, buyer: int, idempotency_key: str) -> None:
    anchor = (await PricingRepository(session).get_rate_table()).anchor
    order = await TransactionRepository(session).create(
        CreateTransactionDto(
            user_id=buyer,
            plan_id=None,
            plan_snapshot=make_plan_snapshot(plan_id=1),
            duration_days=30,
            currency=anchor,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
            gateway_type=PaymentGatewayType.YOOKASSA,
            base_price=Decimal("250"),
            discount_percent=0,
            discount_source=DiscountSource.NONE,
            final_price=Decimal("250"),
            anchor_base_price=Decimal("250"),
            anchor_final_price=Decimal("250"),
            customer_email=None,
            idempotency_key=idempotency_key,
            expires_at=datetime_now() + timedelta(minutes=30),
        )
    )
    await _set_status(session, order.id)


async def _create_user(user_repository: UserRepository, telegram_id: int) -> int:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=telegram_id))
    return user.id


async def _create_active_subscription(
    subscription_repository: SubscriptionRepository,
    user_id: int,
    remnawave_user_id: int,
    price_paid: Decimal = Decimal("100"),
) -> int:
    sub = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user_id,
            remnawave_user_id=remnawave_user_id,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=0,
            device_limit=0,
            expire_at=datetime_now(),
            url="https://example.test/sub",
            plan_snapshot=make_plan_snapshot(plan_id=1, price_paid=price_paid),
        )
    )
    return sub.id


async def test_assign_referral_rewards_skips_when_system_disabled(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    referrer_id = await _create_user(user_repository, 4001)
    buyer_id = await _create_user(user_repository, 4002)
    await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=buyer_id, level=1
    )
    subscription_id = await _create_active_subscription(subscription_repository, buyer_id, 4002)

    await _paid_order(referral_repository.session, buyer_id, "order-1")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer_id,
            subscription_id=subscription_id,
            is_new_purchase=True,
            payment_key="order-1",
        )
    )

    updated_referrer = await user_repository.get_by_id(referrer_id)
    assert updated_referrer.points == Decimal(0)


async def test_assign_referral_rewards_credits_points_up_the_chain(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=2,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10"), 2: Decimal("3")},
        )
    )
    top = await _create_user(user_repository, 4003)
    middle = await _create_user(user_repository, 4004)
    buyer = await _create_user(user_repository, 4005)
    edge_top_middle = await referral_repository.create_referral(
        referrer_id=top, referred_id=middle, level=1
    )
    edge_middle_buyer = await referral_repository.create_referral(
        referrer_id=middle, referred_id=buyer, level=2
    )
    subscription_id = await _create_active_subscription(subscription_repository, buyer, 4005)

    await _paid_order(referral_repository.session, buyer, "order-1")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer,
            subscription_id=subscription_id,
            is_new_purchase=True,
            payment_key="order-1",
        )
    )

    assert (await user_repository.get_by_id(middle)).points == Decimal("10")
    assert (await user_repository.get_by_id(top)).points == Decimal("3")

    # Each reward's referral_id must be the edge that placed its beneficiary
    # at that level (the edge below them), not the edge above them.
    middle_reward = await referral_repository.session.scalar(
        select(ReferralReward).where(ReferralReward.referrer_id == middle)
    )
    top_reward = await referral_repository.session.scalar(
        select(ReferralReward).where(ReferralReward.referrer_id == top)
    )
    assert middle_reward.referral_id == edge_middle_buyer.id
    assert top_reward.referral_id == edge_top_middle.id


async def test_assign_referral_rewards_skips_trial_purchase(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer_id = await _create_user(user_repository, 4006)
    buyer_id = await _create_user(user_repository, 4007)
    await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=buyer_id, level=1
    )
    sub = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer_id,
            remnawave_user_id=4007,
            status=SubscriptionStatus.ACTIVE,
            is_trial=True,
            traffic_limit=0,
            device_limit=0,
            expire_at=datetime_now(),
            url="https://example.test/sub",
            plan_snapshot=make_plan_snapshot(plan_id=1, is_trial=True),
        )
    )

    await _paid_order(referral_repository.session, buyer_id, "order-1")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer_id,
            subscription_id=sub.id,
            is_new_purchase=True,
            payment_key="order-1",
        )
    )

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal(0)


async def test_assign_referral_rewards_first_payment_strategy_skips_renewal(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer_id = await _create_user(user_repository, 4008)
    buyer_id = await _create_user(user_repository, 4009)
    await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=buyer_id, level=1
    )
    subscription_id = await _create_active_subscription(subscription_repository, buyer_id, 4009)

    await _paid_order(referral_repository.session, buyer_id, "order-1")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer_id,
            subscription_id=subscription_id,
            is_new_purchase=False,  # a renewal, not the first purchase
            payment_key="order-1",
        )
    )

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal(0)


async def test_assign_referral_rewards_one_level_failure_does_not_block_the_next(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    monkeypatch,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    # Level 1's grant blows up; level 2 must still be paid, and the failure
    # must reach the caller so the task's own retry can pick it up.
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=2,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("5"), 2: Decimal("7")},
        )
    )
    # Committed, not just flushed: the failing hop below rolls its own
    # transaction back, which would otherwise take this setup with it.
    async with uow:
        top = await _create_user(user_repository, 4010)
        middle = await _create_user(user_repository, 4011)
        buyer = await _create_user(user_repository, 4012)
        await referral_repository.create_referral(referrer_id=top, referred_id=middle, level=1)
        await referral_repository.create_referral(referrer_id=middle, referred_id=buyer, level=2)
        subscription_id = await _create_active_subscription(subscription_repository, buyer, 4012)
        await _paid_order(referral_repository.session, buyer, "order-1")

    real_credit_points = user_repository.credit_points

    async def _failing_credit_points(user_id: int, amount: Decimal) -> None:
        if user_id == middle:
            raise RuntimeError("simulated grant failure")
        await real_credit_points(user_id, amount)

    monkeypatch.setattr(user_repository, "credit_points", _failing_credit_points)

    with pytest.raises(RuntimeError):
        await assign_rewards.system(
            AssignReferralRewardsDto(
                user_id=buyer,
                subscription_id=subscription_id,
                is_new_purchase=True,
                payment_key="order-1",
            )
        )

    rewarded = set(
        (await subscription_repository.session.scalars(select(ReferralReward.referrer_id))).all()
    )
    assert rewarded == {top}
    top_user = await user_repository.get_by_id(top)
    assert top_user is not None
    assert top_user.points == Decimal("7")


async def test_assign_referral_rewards_is_idempotent_against_duplicate_delivery(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer_id = await _create_user(user_repository, 4013)
    buyer_id = await _create_user(user_repository, 4014)
    await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=buyer_id, level=1
    )
    subscription_id = await _create_active_subscription(subscription_repository, buyer_id, 4014)

    await _paid_order(referral_repository.session, buyer_id, "order-1")
    for _ in range(2):
        await assign_rewards.system(
            AssignReferralRewardsDto(
                user_id=buyer_id,
                subscription_id=subscription_id,
                is_new_purchase=True,
                payment_key="order-1",
            )
        )

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal("10")
    rows = (
        await referral_repository.session.scalars(
            select(ReferralReward).where(
                ReferralReward.subscription_id == subscription_id,
                ReferralReward.referrer_id == referrer_id,
            )
        )
    ).all()
    assert len(rows) == 1


async def test_assign_referral_rewards_stops_walk_at_mutual_referral_cycle(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=3,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10"), 2: Decimal("5"), 3: Decimal("2")},
        )
    )
    a = await _create_user(user_repository, 4015)
    b = await _create_user(user_repository, 4016)
    # A refers B, then B refers A: neither has a referrer yet when asked
    await referral_repository.create_referral(referrer_id=a, referred_id=b, level=1)
    await referral_repository.create_referral(referrer_id=b, referred_id=a, level=1)
    subscription_id = await _create_active_subscription(subscription_repository, b, 4016)

    await _paid_order(referral_repository.session, b, "order-1")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=b,
            subscription_id=subscription_id,
            is_new_purchase=True,
            payment_key="order-1",
        )
    )

    # Level 1 (b -> a) rewards a; the walk must stop there instead of looping
    # back to b (the buyer) as a bogus level-2 hop.
    assert (await user_repository.get_by_id(a)).points == Decimal("10")
    assert (await user_repository.get_by_id(b)).points == Decimal(0)


async def test_assign_referral_rewards_every_payment_strategy_rewards_each_renewal(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.EVERY_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer_id = await _create_user(user_repository, 4020)
    buyer_id = await _create_user(user_repository, 4021)
    await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=buyer_id, level=1
    )
    subscription_id = await _create_active_subscription(subscription_repository, buyer_id, 4021)

    for payment_key, is_new_purchase in (("order-1", True), ("order-2", False), ("order-3", False)):
        await _paid_order(referral_repository.session, buyer_id, payment_key)
        await assign_rewards.system(
            AssignReferralRewardsDto(
                user_id=buyer_id,
                subscription_id=subscription_id,
                is_new_purchase=is_new_purchase,
                payment_key=payment_key,
            )
        )

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal("30")


async def test_first_payment_strategy_skips_a_second_paid_subscription(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    # Both are NEW purchases (several concurrent subscriptions are allowed),
    # but only the first one is the buyer's first payment.
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer_id = await _create_user(user_repository, 4020)
    buyer_id = await _create_user(user_repository, 4021)
    await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=buyer_id, level=1
    )
    await _create_active_subscription(subscription_repository, buyer_id, 4021)
    second_subscription_id = await _create_active_subscription(
        subscription_repository, buyer_id, 4022
    )

    await _paid_order(referral_repository.session, buyer_id, "order-2")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer_id,
            subscription_id=second_subscription_id,
            is_new_purchase=True,
            payment_key="order-2",
        )
    )

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal(0)
    assert await referral_repository.list_rewards_by_referrer(referrer_id) == []


async def test_points_reward_is_not_recorded_when_the_credit_fails(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    uow,
    monkeypatch,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    # Ledger row and credit share one transaction, so a failed credit leaves
    # nothing behind to make the retry skip the hop as "already granted".
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    async with uow:
        referrer_id = await _create_user(user_repository, 4030)
        buyer_id = await _create_user(user_repository, 4031)
        await referral_repository.create_referral(
            referrer_id=referrer_id, referred_id=buyer_id, level=1
        )
        subscription_id = await _create_active_subscription(subscription_repository, buyer_id, 4031)
        await _paid_order(referral_repository.session, buyer_id, "order-3")

    real_credit_points = user_repository.credit_points
    failing = True

    async def _flaky_credit_points(user_id: int, amount: Decimal) -> None:
        if failing:
            raise RuntimeError("simulated credit failure")
        await real_credit_points(user_id, amount)

    monkeypatch.setattr(user_repository, "credit_points", _flaky_credit_points)

    data = AssignReferralRewardsDto(
        user_id=buyer_id,
        subscription_id=subscription_id,
        is_new_purchase=True,
        payment_key="order-3",
    )

    with pytest.raises(RuntimeError):
        await assign_rewards.system(data)

    assert await referral_repository.list_rewards_by_referrer(referrer_id) == []

    failing = False
    await assign_rewards.system(data)

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal("10")
    assert len(await referral_repository.list_rewards_by_referrer(referrer_id)) == 1


async def test_assign_referral_rewards_percent_points_from_order_price(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=2,
            accrual_strategy=ReferralAccrualStrategy.EVERY_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_strategy=ReferralRewardStrategy.PERCENT,
            reward_amounts={1: Decimal("10"), 2: Decimal("3")},
        )
    )
    top = await _create_user(user_repository, 4101)
    middle = await _create_user(user_repository, 4102)
    buyer = await _create_user(user_repository, 4103)
    await referral_repository.create_referral(referrer_id=top, referred_id=middle, level=1)
    await referral_repository.create_referral(referrer_id=middle, referred_id=buyer, level=2)
    subscription_id = await _create_active_subscription(subscription_repository, buyer, 4103)
    session = referral_repository.session
    pricing_repository = PricingRepository(session)
    anchor = (await pricing_repository.get_rate_table()).anchor
    transaction_repository = TransactionRepository(session)
    order = await transaction_repository.create(
        CreateTransactionDto(
            user_id=buyer,
            plan_id=None,
            plan_snapshot=make_plan_snapshot(plan_id=1),
            duration_days=30,
            currency=anchor,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
            gateway_type=PaymentGatewayType.YOOKASSA,
            base_price=Decimal("250"),
            discount_percent=0,
            discount_source=DiscountSource.NONE,
            final_price=Decimal("250"),
            anchor_base_price=Decimal("250"),
            anchor_final_price=Decimal("250"),
            customer_email=None,
            idempotency_key="order-percent",
            expires_at=datetime_now() + timedelta(minutes=30),
        )
    )
    await _set_status(session, order.id)

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer,
            subscription_id=subscription_id,
            is_new_purchase=True,
            payment_key="order-percent",
        )
    )

    # 10% of 250 = 25; 3% of 250 = 7.5, rounded down
    assert (await user_repository.get_by_id(middle)).points == Decimal("25")
    assert (await user_repository.get_by_id(top)).points == Decimal("7")


async def test_assign_referral_rewards_percent_points_from_order_anchor_amount(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.EVERY_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_strategy=ReferralRewardStrategy.PERCENT,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer = await _create_user(user_repository, 4111)
    buyer = await _create_user(user_repository, 4112)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    subscription_id = await _create_active_subscription(subscription_repository, buyer, 4112)
    order = await TransactionRepository(referral_repository.session).create(
        CreateTransactionDto(
            user_id=buyer,
            plan_id=None,
            plan_snapshot=make_plan_snapshot(plan_id=1),
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
            gateway_type=PaymentGatewayType.YOOKASSA,
            base_price=Decimal("900"),
            discount_percent=0,
            discount_source=DiscountSource.NONE,
            final_price=Decimal("900"),
            anchor_base_price=Decimal("10"),
            anchor_final_price=Decimal("10"),
            customer_email=None,
            idempotency_key="order-percent-anchor",
            expires_at=datetime_now() + timedelta(minutes=30),
        )
    )
    await _set_status(referral_repository.session, order.id)

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer,
            subscription_id=subscription_id,
            is_new_purchase=True,
            payment_key="order-percent-anchor",
        )
    )

    # 10% of the anchor amount 10, not of the 900 paid in RUB
    assert (await user_repository.get_by_id(referrer)).points == Decimal("1")


def test_level_amounts_percent_of_days_rounds_down_with_a_floor_of_one() -> None:
    settings = ReferralSettingsDto(
        reward_type=ReferralRewardType.EXTRA_DAYS,
        reward_strategy=ReferralRewardStrategy.PERCENT,
        reward_amounts={1: Decimal("50"), 2: Decimal("1"), 3: Decimal("0")},
    )

    assert _level_amounts(settings, Decimal(30)) == {1: Decimal(15), 2: Decimal(1)}
    assert _level_amounts(settings, None) == {}


@pytest.fixture
def attach_on_registration(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> AttachReferralOnRegistrationUseCase:
    return AttachReferralOnRegistrationUseCase(
        referral_repository, user_repository, uow, event_publisher
    )


async def _register(
    attach: AttachReferralOnRegistrationUseCase, newcomer_id: int, code: Optional[str]
) -> None:
    await attach.system(
        AttachReferralOnRegistrationDto(user_id=newcomer_id, referral_code=code or "")
    )


async def _referral_code(user_repository: UserRepository, user_id: int) -> Optional[str]:
    user = await user_repository.get_by_id(user_id)
    assert user is not None
    return user.referral_code


async def test_registration_links_the_newcomer_at_level_one(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
) -> None:
    await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True))
    referrer = await _create_user(user_repository, 4201)
    newcomer = await _create_user(user_repository, 4202)

    await _register(
        attach_on_registration, newcomer, await _referral_code(user_repository, referrer)
    )

    edge = await referral_repository.get_by_referred_id(newcomer)
    assert edge is not None
    assert edge.referrer_id == referrer
    assert edge.level == 1


async def test_registration_level_follows_the_referrers_chain_up_to_max_level(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
) -> None:
    await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True, max_level=2))
    a, b, c, d = [await _create_user(user_repository, 4210 + i) for i in range(4)]
    for parent, child in ((a, b), (b, c), (c, d)):
        await _register(
            attach_on_registration, child, await _referral_code(user_repository, parent)
        )

    assert (await referral_repository.get_by_referred_id(c)).level == 2
    assert (await referral_repository.get_by_referred_id(d)).level == 2  # clamped


async def test_registration_rewards_the_newcomer_with_days(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            invitee_reward_type=ReferralRewardType.EXTRA_DAYS,
            invitee_reward_amount=7,
        )
    )
    referrer = await _create_user(user_repository, 4220)
    newcomer = await _create_user(user_repository, 4221)

    await _register(
        attach_on_registration, newcomer, await _referral_code(user_repository, referrer)
    )

    assert (await user_repository.get_by_id(newcomer)).bonus_days == 7
    assert (await user_repository.get_by_id(referrer)).bonus_days == 0


async def test_registration_rewards_the_newcomer_with_points(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True, invitee_reward_type=ReferralRewardType.POINTS, invitee_reward_amount=50
        )
    )
    referrer = await _create_user(user_repository, 4222)
    newcomer = await _create_user(user_repository, 4223)

    await _register(
        attach_on_registration, newcomer, await _referral_code(user_repository, referrer)
    )

    assert (await user_repository.get_by_id(newcomer)).points == Decimal(50)


async def test_registration_with_a_zero_reward_links_without_crediting(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
) -> None:
    await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True))
    referrer = await _create_user(user_repository, 4224)
    newcomer = await _create_user(user_repository, 4225)

    await _register(
        attach_on_registration, newcomer, await _referral_code(user_repository, referrer)
    )

    assert await referral_repository.get_by_referred_id(newcomer) is not None
    user = await user_repository.get_by_id(newcomer)
    assert user.bonus_days == 0
    assert user.points == Decimal(0)


async def test_a_redelivered_registration_rewards_once(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await referral_repository.update_settings(
            UpdateReferralSettingsDto(enabled=True, invitee_reward_amount=7)
        )
        referrer = await _create_user(user_repository, 4226)
        newcomer = await _create_user(user_repository, 4227)
    code = await _referral_code(user_repository, referrer)

    await _register(attach_on_registration, newcomer, code)
    await _register(attach_on_registration, newcomer, code)

    assert (await user_repository.get_by_id(newcomer)).bonus_days == 7


@pytest.mark.parametrize("case", ["disabled", "unknown", "own", "cycle"])
async def test_registration_with_an_unusable_link_neither_links_nor_rewards(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
    case: str,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(enabled=True, invitee_reward_amount=7)
    )
    other = await _create_user(user_repository, 4230)
    newcomer = await _create_user(user_repository, 4231)
    if case == "cycle":
        # the newcomer already invited `other`; linking back would close a loop
        await _register(
            attach_on_registration, other, await _referral_code(user_repository, newcomer)
        )
    if case == "disabled":
        await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=False))
    code = {
        "disabled": await _referral_code(user_repository, other),
        "unknown": "NOPE0000",
        "own": await _referral_code(user_repository, newcomer),
        "cycle": await _referral_code(user_repository, other),
    }[case]

    await _register(attach_on_registration, newcomer, code)

    assert await referral_repository.get_by_referred_id(newcomer) is None
    assert (await user_repository.get_by_id(newcomer)).bonus_days == 0


def _free_order(buyer: int, idempotency_key: str, currency: Currency) -> CreateTransactionDto:
    return CreateTransactionDto(
        user_id=buyer,
        plan_id=None,
        plan_snapshot=make_plan_snapshot(plan_id=1),
        duration_days=30,
        currency=currency,
        purchase_type=PurchaseType.NEW,
        target_subscription_id=None,
        gateway_type=PaymentGatewayType.YOOKASSA,
        base_price=Decimal("250"),
        discount_percent=100,
        discount_source=DiscountSource.PERSONAL,
        final_price=Decimal("0"),
        anchor_base_price=Decimal("250"),
        anchor_final_price=Decimal("0"),
        customer_email=None,
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_free_order_earns_no_referral_reward(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.EVERY_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_strategy=ReferralRewardStrategy.PERCENT,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer = await _create_user(user_repository, 4301)
    buyer = await _create_user(user_repository, 4302)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    subscription_id = await _create_active_subscription(
        subscription_repository, buyer, 4302, price_paid=Decimal("0")
    )
    session = referral_repository.session
    pricing_repository = PricingRepository(session)
    transaction_repository = TransactionRepository(session)
    anchor = (await pricing_repository.get_rate_table()).anchor
    order = await transaction_repository.create(_free_order(buyer, "order-free", anchor))
    await _set_status(session, order.id)

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer,
            subscription_id=subscription_id,
            is_new_purchase=True,
            payment_key="order-free",
        )
    )

    # PERCENT would otherwise floor at 1 point even on a zero base
    assert (await user_repository.get_by_id(referrer)).points == Decimal(0)


async def test_first_payment_strategy_ignores_an_earlier_free_subscription(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer = await _create_user(user_repository, 4311)
    buyer = await _create_user(user_repository, 4312)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    await _create_active_subscription(subscription_repository, buyer, 4312, price_paid=Decimal("0"))
    paid_subscription_id = await _create_active_subscription(subscription_repository, buyer, 4313)

    await _paid_order(referral_repository.session, buyer, "order-first-paid")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer,
            subscription_id=paid_subscription_id,
            is_new_purchase=True,
            payment_key="order-first-paid",
        )
    )

    assert (await user_repository.get_by_id(referrer)).points == Decimal("10")


async def _enable_day_rewards(
    referral_repository: ReferralRepository, *, require_paid: bool
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.EXTRA_DAYS,
            reward_amounts={1: Decimal("7")},
            days_require_paid_subscription=require_paid,
        )
    )


async def test_day_reward_goes_to_the_balance_not_a_subscription(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await _enable_day_rewards(referral_repository, require_paid=True)
    referrer = await _create_user(user_repository, 4101)
    buyer = await _create_user(user_repository, 4102)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    referrer_sub = await _create_active_subscription(subscription_repository, referrer, 4101)
    before = await subscription_repository.get_by_id(referrer_sub)
    buyer_sub = await _create_active_subscription(subscription_repository, buyer, 4102)

    await _paid_order(referral_repository.session, buyer, "d-1")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer, subscription_id=buyer_sub, is_new_purchase=True, payment_key="d-1"
        )
    )

    assert (await user_repository.get_by_id(referrer)).bonus_days == 7
    after = await subscription_repository.get_by_id(referrer_sub)
    assert after.expire_at == before.expire_at
    reward = await referral_repository.session.scalar(
        select(ReferralReward).where(ReferralReward.referrer_id == referrer)
    )
    assert reward.type is ReferralRewardType.EXTRA_DAYS
    assert reward.amount == Decimal("7")


async def test_day_reward_skipped_for_a_referrer_who_never_paid(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await _enable_day_rewards(referral_repository, require_paid=True)
    referrer = await _create_user(user_repository, 4103)
    buyer = await _create_user(user_repository, 4104)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    # a free subscription doesn't make the referrer a paying one
    await _create_active_subscription(
        subscription_repository, referrer, 4103, price_paid=Decimal(0)
    )
    buyer_sub = await _create_active_subscription(subscription_repository, buyer, 4104)

    await _paid_order(referral_repository.session, buyer, "d-2")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer, subscription_id=buyer_sub, is_new_purchase=True, payment_key="d-2"
        )
    )

    assert (await user_repository.get_by_id(referrer)).bonus_days == 0
    rows = (
        await referral_repository.session.scalars(
            select(ReferralReward).where(ReferralReward.referrer_id == referrer)
        )
    ).all()
    assert rows == []


async def test_day_reward_credited_without_any_subscription_when_not_required(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await _enable_day_rewards(referral_repository, require_paid=False)
    referrer = await _create_user(user_repository, 4105)
    buyer = await _create_user(user_repository, 4106)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    buyer_sub = await _create_active_subscription(subscription_repository, buyer, 4106)

    await _paid_order(referral_repository.session, buyer, "d-3")
    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer, subscription_id=buyer_sub, is_new_purchase=True, payment_key="d-3"
        )
    )

    assert (await user_repository.get_by_id(referrer)).bonus_days == 7


async def test_day_reward_is_not_credited_twice_for_one_payment(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await _enable_day_rewards(referral_repository, require_paid=False)
    referrer = await _create_user(user_repository, 4107)
    buyer = await _create_user(user_repository, 4108)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    buyer_sub = await _create_active_subscription(subscription_repository, buyer, 4108)

    await _paid_order(referral_repository.session, buyer, "d-4")
    for _ in range(2):
        await assign_rewards.system(
            AssignReferralRewardsDto(
                user_id=buyer, subscription_id=buyer_sub, is_new_purchase=True, payment_key="d-4"
            )
        )

    assert (await user_repository.get_by_id(referrer)).bonus_days == 7


async def test_renewal_without_an_order_earns_no_reward(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    # a bonus-day redemption renews with a key but no paid order behind it
    await _enable_day_rewards(referral_repository, require_paid=False)
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(accrual_strategy=ReferralAccrualStrategy.EVERY_PAYMENT)
    )
    referrer = await _create_user(user_repository, 4109)
    buyer = await _create_user(user_repository, 4110)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    buyer_sub = await _create_active_subscription(subscription_repository, buyer, 4110)

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer, subscription_id=buyer_sub, is_new_purchase=False, payment_key="no-order"
        )
    )

    assert (await user_repository.get_by_id(referrer)).bonus_days == 0


async def test_day_reward_skipped_for_a_referrer_with_only_a_trial(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await _enable_day_rewards(referral_repository, require_paid=True)
    referrer = await _create_user(user_repository, 4111)
    buyer = await _create_user(user_repository, 4112)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=referrer,
            remnawave_user_id=4111,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=0,
            device_limit=0,
            expire_at=datetime_now(),
            url="https://example.test/sub",
            plan_snapshot=make_plan_snapshot(plan_id=1, price_paid=Decimal("100")),
            is_trial=True,
        )
    )
    buyer_sub = await _create_active_subscription(subscription_repository, buyer, 4112)
    await _paid_order(referral_repository.session, buyer, "d-5")

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer, subscription_id=buyer_sub, is_new_purchase=True, payment_key="d-5"
        )
    )

    assert (await user_repository.get_by_id(referrer)).bonus_days == 0


async def test_deleted_referrer_earns_nothing(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await _enable_day_rewards(referral_repository, require_paid=False)
    referrer = await _create_user(user_repository, 4113)
    buyer = await _create_user(user_repository, 4114)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    await user_repository.anonymize(referrer)
    buyer_sub = await _create_active_subscription(subscription_repository, buyer, 4114)
    await _paid_order(referral_repository.session, buyer, "d-6")

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer, subscription_id=buyer_sub, is_new_purchase=True, payment_key="d-6"
        )
    )

    assert (await user_repository.get_by_id(referrer)).bonus_days == 0
    assert await referral_repository.list_rewards_by_referrer(referrer) == []


async def test_a_blocked_referrers_link_neither_links_nor_rewards(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(enabled=True, invitee_reward_amount=7)
    )
    referrer = await _create_user(user_repository, 4240)
    newcomer = await _create_user(user_repository, 4241)
    await user_repository.set_blocked(referrer, True)

    code = await _referral_code(user_repository, referrer)
    await _register(attach_on_registration, newcomer, code)

    assert await referral_repository.get_by_referred_id(newcomer) is None
    assert (await user_repository.get_by_id(newcomer)).bonus_days == 0


async def test_a_deleted_newcomer_is_not_linked(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    attach_on_registration: AttachReferralOnRegistrationUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(enabled=True, invitee_reward_amount=7)
    )
    referrer = await _create_user(user_repository, 4242)
    newcomer = await _create_user(user_repository, 4243)
    code = await _referral_code(user_repository, referrer)
    await user_repository.anonymize(newcomer)

    await _register(attach_on_registration, newcomer, code)

    assert await referral_repository.get_by_referred_id(newcomer) is None


async def test_a_blocked_referrer_earns_nothing_from_payments(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await _enable_day_rewards(referral_repository, require_paid=False)
    referrer = await _create_user(user_repository, 4244)
    buyer = await _create_user(user_repository, 4245)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    await user_repository.set_blocked(referrer, True)
    buyer_sub = await _create_active_subscription(subscription_repository, buyer, 4245)
    await _paid_order(referral_repository.session, buyer, "d-7")

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer, subscription_id=buyer_sub, is_new_purchase=True, payment_key="d-7"
        )
    )

    assert (await user_repository.get_by_id(referrer)).bonus_days == 0
    assert await referral_repository.list_rewards_by_referrer(referrer) == []


async def test_refunded_order_earns_no_referral_reward(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.EVERY_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_strategy=ReferralRewardStrategy.AMOUNT,
            reward_amounts={1: Decimal("5")},
        )
    )
    referrer = await _create_user(user_repository, 4401)
    buyer = await _create_user(user_repository, 4402)
    await referral_repository.create_referral(referrer_id=referrer, referred_id=buyer, level=1)
    subscription_id = await _create_active_subscription(subscription_repository, buyer, 4402)
    session = referral_repository.session
    await _paid_order(session, buyer, "order-refunded")
    order = await TransactionRepository(session).get_by_idempotency_key("order-refunded")
    assert order is not None
    await _set_status(session, order.id, TransactionStatus.REFUNDED)

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer,
            subscription_id=subscription_id,
            is_new_purchase=True,
            payment_key="order-refunded",
        )
    )

    assert (await user_repository.get_by_id(referrer)).points == Decimal(0)


async def test_first_payment_rewards_the_earlier_of_two_paid_subscriptions(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    referrer_id = await _create_user(user_repository, 4091)
    buyer_id = await _create_user(user_repository, 4092)
    await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=buyer_id, level=1
    )
    # both bought before either reward ran
    first = await _create_active_subscription(subscription_repository, buyer_id, 4092)
    second = await _create_active_subscription(subscription_repository, buyer_id, 4093)
    await _paid_order(referral_repository.session, buyer_id, "order-1")
    await _paid_order(referral_repository.session, buyer_id, "order-2")

    for subscription_id, key in ((first, "order-1"), (second, "order-2")):
        await assign_rewards.system(
            AssignReferralRewardsDto(
                user_id=buyer_id,
                subscription_id=subscription_id,
                is_new_purchase=True,
                payment_key=key,
            )
        )

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal("10")
    rewarded = await referral_repository.session.scalars(
        select(ReferralReward.subscription_id).where(ReferralReward.referrer_id == referrer_id)
    )
    assert rewarded.all() == [first]


async def test_assign_referral_rewards_skips_an_order_refunded_while_assigning(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    assign_rewards: AssignReferralRewardsUseCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=1,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.POINTS,
            reward_amounts={1: Decimal("10")},
        )
    )
    inviter = await _create_user(user_repository, 4060)
    buyer = await _create_user(user_repository, 4061)
    await referral_repository.create_referral(referrer_id=inviter, referred_id=buyer, level=1)
    subscription_id = await _create_active_subscription(subscription_repository, buyer, 4061)
    session = referral_repository.session
    await _paid_order(session, buyer, "order-refunded-midway")
    order = await TransactionRepository(session).get_by_idempotency_key("order-refunded-midway")
    real_walk = assign_rewards._walk_chain

    async def _walk_then_refund(*args: object) -> object:
        chain = await real_walk(*args)
        # the refund webhook lands after the first PAID check
        await _set_status(session, order.id, TransactionStatus.REFUNDED)
        return chain

    monkeypatch.setattr(assign_rewards, "_walk_chain", _walk_then_refund)

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer,
            subscription_id=subscription_id,
            is_new_purchase=True,
            payment_key="order-refunded-midway",
        )
    )

    assert (await user_repository.get_by_id(inviter)).points == Decimal("0")
    assert (
        await session.scalar(select(ReferralReward).where(ReferralReward.referrer_id == inviter))
    ) is None
