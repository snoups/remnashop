from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

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
from app.modules.referrals.usecases.attach_referral import AttachReferralUseCase
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
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
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> AssignReferralRewardsUseCase:
    session = referral_repository.session
    return AssignReferralRewardsUseCase(
        referral_repository,
        TransactionRepository(session),
        PricingRepository(session),
        user_repository,
        subscription_repository,
        purchase_subscription_use_case,
        uow,
        event_publisher,
    )


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
    # A refers B, then (separately) B refers A -- neither call violates
    # "already has a referrer" since each checks only the other's own edge.
    await referral_repository.create_referral(referrer_id=a, referred_id=b, level=1)
    await referral_repository.create_referral(referrer_id=b, referred_id=a, level=1)
    subscription_id = await _create_active_subscription(subscription_repository, b, 4016)

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
    await transaction_repository.create(
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
            customer_email=None,
            idempotency_key="order-percent",
            expires_at=datetime_now() + timedelta(minutes=30),
        )
    )

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


def test_level_amounts_percent_of_days_rounds_down_with_a_floor_of_one() -> None:
    settings = ReferralSettingsDto(
        reward_type=ReferralRewardType.EXTRA_DAYS,
        reward_strategy=ReferralRewardStrategy.PERCENT,
        reward_amounts={1: Decimal("50"), 2: Decimal("1"), 3: Decimal("0")},
    )

    assert _level_amounts(settings, Decimal(30)) == {1: Decimal(15), 2: Decimal(1)}
    assert _level_amounts(settings, None) == {}


async def test_attach_referral_on_registration_links_the_new_user(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow,
    event_publisher,
) -> None:
    await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True))
    referrer = await user_repository.create(CreateUserDto(name="r", telegram_id=4201))
    newcomer_id = await _create_user(user_repository, 4202)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)

    await AttachReferralOnRegistrationUseCase(user_repository, use_case).system(
        AttachReferralOnRegistrationDto(user_id=newcomer_id, referral_code=referrer.referral_code)
    )

    edge = await referral_repository.get_by_referred_id(newcomer_id)
    assert edge is not None
    assert edge.referrer_id == referrer.id


async def test_attach_referral_on_registration_ignores_an_unknown_code(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow,
    event_publisher,
) -> None:
    await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True))
    newcomer_id = await _create_user(user_repository, 4203)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)

    await AttachReferralOnRegistrationUseCase(user_repository, use_case).system(
        AttachReferralOnRegistrationDto(user_id=newcomer_id, referral_code="NOPE0000")
    )

    assert await referral_repository.get_by_referred_id(newcomer_id) is None


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
    await transaction_repository.create(_free_order(buyer, "order-free", anchor))

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

    await assign_rewards.system(
        AssignReferralRewardsDto(
            user_id=buyer,
            subscription_id=paid_subscription_id,
            is_new_purchase=True,
            payment_key="order-first-paid",
        )
    )

    assert (await user_repository.get_by_id(referrer)).points == Decimal("10")
