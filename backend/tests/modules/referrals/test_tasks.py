from decimal import Decimal

from sqlalchemy import select

from app.core.db.models.referral_reward import ReferralReward
from app.core.enums import ReferralAccrualStrategy, ReferralRewardType, SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.referrals.dto import UpdateReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.tasks import assign_referral_rewards
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import PurchaseSubscriptionUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot


def _purchase_use_case(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> PurchaseSubscriptionUseCase:
    return PurchaseSubscriptionUseCase(
        subscription_repository,
        user_repository,
        SettingsRepository(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )


async def _create_user(user_repository: UserRepository, telegram_id: int) -> int:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=telegram_id))
    return user.id


async def _create_active_subscription(
    subscription_repository: SubscriptionRepository, user_id: int, remnawave_user_id: int
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
            plan_snapshot=make_plan_snapshot(plan_id=1),
        )
    )
    return sub.id


async def test_assign_referral_rewards_skips_when_system_disabled(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    referrer_id = await _create_user(user_repository, 4001)
    buyer_id = await _create_user(user_repository, 4002)
    await referral_repository.create_referral(
        referrer_id=referrer_id, referred_id=buyer_id, level=1
    )
    subscription_id = await _create_active_subscription(subscription_repository, buyer_id, 4002)

    await assign_referral_rewards(
        referral_repository=referral_repository,
        user_repository=user_repository,
        subscription_repository=subscription_repository,
        purchase_subscription_use_case=_purchase_use_case(
            subscription_repository, user_repository, remnawave_sdk, uow, event_publisher
        ),
        uow=uow,
        event_publisher=event_publisher,
        user_id=buyer_id,
        subscription_id=subscription_id,
        is_new_purchase=True,
    )

    updated_referrer = await user_repository.get_by_id(referrer_id)
    assert updated_referrer.points == Decimal(0)


async def test_assign_referral_rewards_credits_points_up_the_chain(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk,
    uow,
    event_publisher,
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

    await assign_referral_rewards(
        referral_repository=referral_repository,
        user_repository=user_repository,
        subscription_repository=subscription_repository,
        purchase_subscription_use_case=_purchase_use_case(
            subscription_repository, user_repository, remnawave_sdk, uow, event_publisher
        ),
        uow=uow,
        event_publisher=event_publisher,
        user_id=buyer,
        subscription_id=subscription_id,
        is_new_purchase=True,
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
    remnawave_sdk,
    uow,
    event_publisher,
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

    await assign_referral_rewards(
        referral_repository=referral_repository,
        user_repository=user_repository,
        subscription_repository=subscription_repository,
        purchase_subscription_use_case=_purchase_use_case(
            subscription_repository, user_repository, remnawave_sdk, uow, event_publisher
        ),
        uow=uow,
        event_publisher=event_publisher,
        user_id=buyer_id,
        subscription_id=sub.id,
        is_new_purchase=True,
    )

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal(0)


async def test_assign_referral_rewards_first_payment_strategy_skips_renewal(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk,
    uow,
    event_publisher,
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

    await assign_referral_rewards(
        referral_repository=referral_repository,
        user_repository=user_repository,
        subscription_repository=subscription_repository,
        purchase_subscription_use_case=_purchase_use_case(
            subscription_repository, user_repository, remnawave_sdk, uow, event_publisher
        ),
        uow=uow,
        event_publisher=event_publisher,
        user_id=buyer_id,
        subscription_id=subscription_id,
        is_new_purchase=False,  # a renewal, not the first purchase
    )

    assert (await user_repository.get_by_id(referrer_id)).points == Decimal(0)


async def test_assign_referral_rewards_one_level_failure_does_not_block_the_next(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk,
    uow,
    event_publisher,
) -> None:
    # Level 1 reward_type EXTRA_DAYS but the referrer has no active
    # subscription to renew -- that hop must fail without blocking level 2.
    await referral_repository.update_settings(
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=2,
            accrual_strategy=ReferralAccrualStrategy.FIRST_PAYMENT,
            reward_type=ReferralRewardType.EXTRA_DAYS,
            reward_amounts={1: Decimal("5"), 2: Decimal("5")},
        )
    )
    top = await _create_user(user_repository, 4010)
    middle = await _create_user(user_repository, 4011)  # never gets an active subscription
    buyer = await _create_user(user_repository, 4012)
    await referral_repository.create_referral(referrer_id=top, referred_id=middle, level=1)
    await referral_repository.create_referral(referrer_id=middle, referred_id=buyer, level=2)
    await _create_active_subscription(subscription_repository, top, 4010)
    subscription_id = await _create_active_subscription(subscription_repository, buyer, 4012)

    # Must not raise, despite level 1 failing.
    await assign_referral_rewards(
        referral_repository=referral_repository,
        user_repository=user_repository,
        subscription_repository=subscription_repository,
        purchase_subscription_use_case=_purchase_use_case(
            subscription_repository, user_repository, remnawave_sdk, uow, event_publisher
        ),
        uow=uow,
        event_publisher=event_publisher,
        user_id=buyer,
        subscription_id=subscription_id,
        is_new_purchase=True,
    )


async def test_assign_referral_rewards_is_idempotent_against_duplicate_delivery(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk,
    uow,
    event_publisher,
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
        await assign_referral_rewards(
            referral_repository=referral_repository,
            user_repository=user_repository,
            subscription_repository=subscription_repository,
            purchase_subscription_use_case=_purchase_use_case(
                subscription_repository, user_repository, remnawave_sdk, uow, event_publisher
            ),
            uow=uow,
            event_publisher=event_publisher,
            user_id=buyer_id,
            subscription_id=subscription_id,
            is_new_purchase=True,
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
    remnawave_sdk,
    uow,
    event_publisher,
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

    await assign_referral_rewards(
        referral_repository=referral_repository,
        user_repository=user_repository,
        subscription_repository=subscription_repository,
        purchase_subscription_use_case=_purchase_use_case(
            subscription_repository, user_repository, remnawave_sdk, uow, event_publisher
        ),
        uow=uow,
        event_publisher=event_publisher,
        user_id=b,
        subscription_id=subscription_id,
        is_new_purchase=True,
    )

    # Level 1 (b -> a) rewards a; the walk must stop there instead of looping
    # back to b (the buyer) as a bogus level-2 hop.
    assert (await user_repository.get_by_id(a)).points == Decimal("10")
    assert (await user_repository.get_by_id(b)).points == Decimal(0)
