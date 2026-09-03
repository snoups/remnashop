from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import SyntheticActor
from app.core.db.models import EventOutboxEntry, User
from app.core.enums import Locale, ReferralRewardType, Role, SubscriptionStatus
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.referrals.dto import UpdateReferralSettingsDto
from app.modules.referrals.events import UserPointsAdjustedEvent
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases.adjust_user_points import (
    AdjustUserPointsDto,
    AdjustUserPointsUseCase,
)
from app.modules.referrals.usecases.attach_referral import AttachReferralDto, AttachReferralUseCase
from app.modules.referrals.usecases.get_own_referral_stats import GetOwnReferralStatsUseCase
from app.modules.referrals.usecases.get_referral_settings import GetReferralSettingsUseCase
from app.modules.referrals.usecases.get_user_referral_stats import GetUserReferralStatsUseCase
from app.modules.referrals.usecases.request_points_withdrawal import (
    RequestPointsWithdrawalDto,
    RequestPointsWithdrawalUseCase,
)
from app.modules.referrals.usecases.update_referral_settings import UpdateReferralSettingsUseCase
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


@pytest.fixture(autouse=True)
async def _seed_owner_row(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK into users, and OWNER acts as the
    # publishing actor in the points-adjustment tests below.
    session.add(
        User(
            id=OWNER.id,
            login=OWNER.login,
            name=OWNER.name,
            role=Role.USER,
            language=OWNER.language,
            is_blocked=False,
        )
    )
    await session.flush()


async def _create_user(user_repository: UserRepository, telegram_id: int) -> UserDto:
    return await user_repository.create(CreateUserDto(name="u", telegram_id=telegram_id))


async def _create_subscription(
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


async def _enabled_settings(referral_repository: ReferralRepository) -> None:
    await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True, max_level=3))


async def test_attach_referral_creates_level_one_edge(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow, event_publisher
) -> None:
    await _enabled_settings(referral_repository)
    referrer = await _create_user(user_repository, 3001)
    referred = await _create_user(user_repository, 3002)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)

    result = await use_case(referred, AttachReferralDto(code=referrer.referral_code))

    assert result is not None
    assert result.id == referrer.id
    edge = await referral_repository.get_by_referred_id(referred.id)
    assert edge is not None
    assert edge.referrer_id == referrer.id
    assert edge.level == 1


async def test_attach_referral_computes_deeper_level_from_referrers_own_chain(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow, event_publisher
) -> None:
    await _enabled_settings(referral_repository)
    top = await _create_user(user_repository, 3003)
    middle = await _create_user(user_repository, 3004)
    bottom = await _create_user(user_repository, 3005)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)
    await use_case(middle, AttachReferralDto(code=top.referral_code))

    await use_case(bottom, AttachReferralDto(code=middle.referral_code))

    edge = await referral_repository.get_by_referred_id(bottom.id)
    assert edge is not None
    assert edge.level == 2


async def test_attach_referral_clamps_at_max_level(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow, event_publisher
) -> None:
    await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True, max_level=2))
    a = await _create_user(user_repository, 3006)
    b = await _create_user(user_repository, 3007)
    c = await _create_user(user_repository, 3008)
    d = await _create_user(user_repository, 3009)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)
    await use_case(b, AttachReferralDto(code=a.referral_code))
    await use_case(c, AttachReferralDto(code=b.referral_code))  # level 2

    await use_case(d, AttachReferralDto(code=c.referral_code))  # would be level 3

    edge = await referral_repository.get_by_referred_id(d.id)
    assert edge is not None
    assert edge.level == 2  # clamped, not 3


async def test_attach_referral_rejects_self_referral(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow, event_publisher
) -> None:
    await _enabled_settings(referral_repository)
    user = await _create_user(user_repository, 3010)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(user, AttachReferralDto(code=user.referral_code))


async def test_attach_referral_rejects_second_attach(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow, event_publisher
) -> None:
    await _enabled_settings(referral_repository)
    referrer_a = await _create_user(user_repository, 3011)
    referrer_b = await _create_user(user_repository, 3012)
    referred = await _create_user(user_repository, 3013)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)
    await use_case(referred, AttachReferralDto(code=referrer_a.referral_code))

    with pytest.raises(ValidationError):
        await use_case(referred, AttachReferralDto(code=referrer_b.referral_code))


async def test_attach_referral_rejects_when_system_disabled(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow, event_publisher
) -> None:
    referrer = await _create_user(user_repository, 3014)
    referred = await _create_user(user_repository, 3015)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(referred, AttachReferralDto(code=referrer.referral_code))


async def test_attach_referral_rejects_unknown_code(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow, event_publisher
) -> None:
    await _enabled_settings(referral_repository)
    referred = await _create_user(user_repository, 3016)
    use_case = AttachReferralUseCase(referral_repository, user_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(referred, AttachReferralDto(code="NOPE0000"))


async def test_request_withdrawal_rejects_amount_above_points(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    user = await _create_user(user_repository, 5001)
    use_case = RequestPointsWithdrawalUseCase(uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(user, RequestPointsWithdrawalDto(amount=Decimal("1")))


async def test_request_withdrawal_does_not_touch_points(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    user = await _create_user(user_repository, 5002)
    await user_repository.credit_points(user.id, Decimal("50"))
    refreshed = await user_repository.get_by_id(user.id)
    use_case = RequestPointsWithdrawalUseCase(uow, event_publisher)

    await use_case(refreshed, RequestPointsWithdrawalDto(amount=Decimal("20")))

    unchanged = await user_repository.get_by_id(user.id)
    assert unchanged.points == Decimal("50")


async def test_adjust_user_points_requires_permission(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    target = await _create_user(user_repository, 5003)
    regular_actor = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(regular_actor, AdjustUserPointsDto(user_id=target.id, delta=Decimal("10")))


async def test_adjust_user_points_owner_can_increase_and_decrease(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    target = await _create_user(user_repository, 5004)
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    await use_case(OWNER, AdjustUserPointsDto(user_id=target.id, delta=Decimal("30")))
    await use_case(OWNER, AdjustUserPointsDto(user_id=target.id, delta=Decimal("-10")))

    updated = await user_repository.get_by_id(target.id)
    assert updated.points == Decimal("20")


async def test_adjust_user_points_below_zero_raises_validation_error(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    target = await _create_user(user_repository, 5005)
    await user_repository.credit_points(target.id, Decimal("10"))
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(OWNER, AdjustUserPointsDto(user_id=target.id, delta=Decimal("-20")))

    unchanged = await user_repository.get_by_id(target.id)
    assert unchanged.points == Decimal("10")


async def test_adjust_user_points_publishes_event(
    user_repository: UserRepository, uow, event_publisher, session
) -> None:
    target = await _create_user(user_repository, 5006)
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    await use_case(OWNER, AdjustUserPointsDto(user_id=target.id, delta=Decimal("15")))

    rows = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == UserPointsAdjustedEvent.__name__
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["delta"] == "15"


async def test_get_referral_settings_requires_permission(
    referral_repository: ReferralRepository,
) -> None:
    use_case = GetReferralSettingsUseCase(referral_repository)
    regular_actor = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)

    with pytest.raises(PermissionDeniedError):
        await use_case(regular_actor)


async def test_update_referral_settings_persists_changes(
    referral_repository: ReferralRepository, uow
) -> None:
    use_case = UpdateReferralSettingsUseCase(referral_repository, uow)

    result = await use_case(OWNER, UpdateReferralSettingsDto(enabled=True, max_level=2))

    assert result.enabled is True
    assert result.max_level == 2


async def test_get_own_referral_stats_reflects_referrer_and_counts(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    referrer = await _create_user(user_repository, 6001)
    a = await _create_user(user_repository, 6002)
    b = await _create_user(user_repository, 6003)
    await referral_repository.create_referral(referrer_id=referrer.id, referred_id=a.id, level=1)
    await referral_repository.create_referral(referrer_id=referrer.id, referred_id=b.id, level=1)
    use_case = GetOwnReferralStatsUseCase(referral_repository)

    stats = await use_case(referrer)

    assert stats.referral_code == referrer.referral_code
    assert stats.counts_by_level == {1: 2}
    assert stats.rewards == []


async def test_get_own_referral_stats_includes_reward_history(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    referrer = await _create_user(user_repository, 6005)
    referred = await _create_user(user_repository, 6006)
    edge = await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=referred.id, level=1
    )
    subscription_id = await _create_subscription(subscription_repository, referred.id, 6006)
    await referral_repository.create_reward(
        referral_id=edge.id,
        referrer_id=referrer.id,
        subscription_id=subscription_id,
        type=ReferralRewardType.POINTS,
        amount=Decimal("7.50"),
    )
    use_case = GetOwnReferralStatsUseCase(referral_repository)

    stats = await use_case(referrer)

    assert len(stats.rewards) == 1
    assert stats.rewards[0].amount == Decimal("7.50")


async def test_get_own_referral_stats_tolerates_synthetic_actor(
    referral_repository: ReferralRepository,
) -> None:
    token_actor = SyntheticActor(
        id=0, role=Role.USER, name="API Token: ci", is_privileged=True, log="[api_token:ci]"
    )
    use_case = GetOwnReferralStatsUseCase(referral_repository)

    stats = await use_case(token_actor)

    assert stats.referral_code is None
    assert stats.points == Decimal(0)


async def test_request_withdrawal_tolerates_synthetic_actor(uow, event_publisher) -> None:
    token_actor = SyntheticActor(
        id=0, role=Role.USER, name="API Token: ci", is_privileged=True, log="[api_token:ci]"
    )
    use_case = RequestPointsWithdrawalUseCase(uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(token_actor, RequestPointsWithdrawalDto(amount=Decimal("1")))


async def test_get_user_referral_stats_requires_permission(
    referral_repository: ReferralRepository, user_repository: UserRepository
) -> None:
    target = await _create_user(user_repository, 6004)
    use_case = GetUserReferralStatsUseCase(referral_repository, user_repository)
    regular_actor = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)

    with pytest.raises(PermissionDeniedError):
        await use_case(regular_actor, target.id)


async def test_get_user_referral_stats_includes_reward_history(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    referrer = await _create_user(user_repository, 6007)
    referred = await _create_user(user_repository, 6008)
    edge = await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=referred.id, level=1
    )
    subscription_id = await _create_subscription(subscription_repository, referred.id, 6008)
    await referral_repository.create_reward(
        referral_id=edge.id,
        referrer_id=referrer.id,
        subscription_id=subscription_id,
        type=ReferralRewardType.POINTS,
        amount=Decimal("9"),
    )
    use_case = GetUserReferralStatsUseCase(referral_repository, user_repository)

    stats = await use_case(OWNER, referrer.id)

    assert len(stats.rewards) == 1
    assert stats.rewards[0].amount == Decimal("9")
