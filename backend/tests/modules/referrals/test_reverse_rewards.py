from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.db.models import EventOutboxEntry
from app.core.db.models.referral_reward import ReferralReward
from app.core.db.uow import UnitOfWork
from app.core.enums import ReferralRewardType
from app.core.ports import EventPublisher
from app.modules.referrals.dto import ReverseReferralRewardsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases import ReverseReferralRewardsUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
def reverse_rewards(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> ReverseReferralRewardsUseCase:
    return ReverseReferralRewardsUseCase(referral_repository, user_repository, uow, event_publisher)


async def _user(user_repository: UserRepository, telegram_id: int) -> int:
    return (await user_repository.create(CreateUserDto(name="u", telegram_id=telegram_id))).id


async def _reward(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    reward_type: ReferralRewardType,
    amount: int,
    telegram_id: int,
) -> tuple[int, int]:
    referrer = await _user(user_repository, telegram_id)
    buyer = await _user(user_repository, telegram_id + 1)
    referral = await referral_repository.create_referral(
        referrer_id=referrer, referred_id=buyer, level=1
    )
    await referral_repository.create_reward(
        referral_id=referral.id,
        referrer_id=referrer,
        subscription_id=None,  # type: ignore[arg-type]
        payment_key="pay-1",
        type=reward_type,
        amount=Decimal(amount),
    )
    if reward_type is ReferralRewardType.EXTRA_DAYS:
        await user_repository.credit_bonus_days(referrer, amount)
    else:
        await user_repository.credit_points(referrer, Decimal(amount))
    return referrer, referral.id


async def _reversed_events(session) -> list[EventOutboxEntry]:  # type: ignore[no-untyped-def]
    rows = await session.scalars(
        select(EventOutboxEntry).where(EventOutboxEntry.event_type == "ReferralRewardReversedEvent")
    )
    return list(rows)


async def test_reverse_takes_what_is_left_and_floors_at_zero(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    reverse_rewards: ReverseReferralRewardsUseCase,
) -> None:
    referrer, _ = await _reward(
        referral_repository, user_repository, ReferralRewardType.EXTRA_DAYS, 30, 5001
    )
    await user_repository.credit_bonus_days(referrer, -20)  # spent

    await reverse_rewards.system(ReverseReferralRewardsDto(payment_key="pay-1"))

    assert (await user_repository.find_by_id(referrer)).bonus_days == 0
    session = referral_repository.session
    row = (await session.scalars(select(ReferralReward))).one()
    assert row.reversed_at is not None
    events = await _reversed_events(session)
    assert len(events) == 1
    assert events[0].payload["amount"] == "10"
    assert events[0].payload["payment_key"] == "pay-1"


async def test_second_reverse_does_nothing(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    reverse_rewards: ReverseReferralRewardsUseCase,
) -> None:
    referrer, _ = await _reward(
        referral_repository, user_repository, ReferralRewardType.EXTRA_DAYS, 30, 5011
    )
    await reverse_rewards.system(ReverseReferralRewardsDto(payment_key="pay-1"))
    await user_repository.credit_bonus_days(referrer, 7)  # unrelated later grant

    await reverse_rewards.system(ReverseReferralRewardsDto(payment_key="pay-1"))

    assert (await user_repository.find_by_id(referrer)).bonus_days == 7
    assert len(await _reversed_events(referral_repository.session)) == 1


async def test_reverse_debits_points(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    reverse_rewards: ReverseReferralRewardsUseCase,
) -> None:
    referrer, _ = await _reward(
        referral_repository, user_repository, ReferralRewardType.POINTS, 50, 5021
    )
    await user_repository.credit_points(referrer, Decimal(-45))

    await reverse_rewards.system(ReverseReferralRewardsDto(payment_key="pay-1"))

    assert (await user_repository.find_by_id(referrer)).points == Decimal(0)
    events = await _reversed_events(referral_repository.session)
    assert len(events) == 1
    assert events[0].payload["amount"] == "5"


async def test_reversed_reward_is_excluded_from_lists_and_summary(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    reverse_rewards: ReverseReferralRewardsUseCase,
) -> None:
    referrer, _ = await _reward(
        referral_repository, user_repository, ReferralRewardType.POINTS, 50, 5031
    )
    assert len(await referral_repository.list_rewards_by_referrer(referrer)) == 1

    await reverse_rewards.system(ReverseReferralRewardsDto(payment_key="pay-1"))

    assert await referral_repository.list_rewards_by_referrer(referrer) == []
    summary = await referral_repository.summarize()
    assert summary.rewarded_count == 0
    assert summary.reward_amounts.get(ReferralRewardType.POINTS, Decimal(0)) == 0
