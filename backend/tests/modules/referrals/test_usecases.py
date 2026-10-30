from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry, User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    ReferralRewardStrategy,
    ReferralRewardType,
    Role,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    CooldownError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.utils.time import datetime_now
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.referrals.dto import (
    MAX_BONUS_DAYS,
    AdjustUserBonusDaysDto,
    AdjustUserPointsDto,
    ListInvitedUsersDto,
    ListReferralsDto,
    UpdateReferralSettingsDto,
)
from app.modules.referrals.events import ReferralCodeResetEvent, UserPointsAdjustedEvent
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases import (
    AdjustUserBonusDaysUseCase,
    AdjustUserPointsUseCase,
    GetOwnReferralStatsUseCase,
    GetReferralSettingsUseCase,
    GetUserReferralRevenueUseCase,
    GetUserReferralStatsUseCase,
    ListInvitedUsersUseCase,
    ListReferralsUseCase,
    ResetOwnReferralCodeUseCase,
    ResetReferralCodeUseCase,
    ResetReferralSettingsUseCase,
    UpdateReferralSettingsUseCase,
)
from app.modules.settings import SettingsRepository
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
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


async def test_adjust_user_points_requires_permission(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    target = await _create_user(user_repository, 5003)
    regular_actor = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            regular_actor,
            AdjustUserPointsDto(user_id=target.id, delta=Decimal("10"), client_ip="127.0.0.1"),
        )


async def test_adjust_user_points_owner_can_increase_and_decrease(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    target = await _create_user(user_repository, 5004)
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    await use_case(
        OWNER, AdjustUserPointsDto(user_id=target.id, delta=Decimal("30"), client_ip="127.0.0.1")
    )
    await use_case(
        OWNER, AdjustUserPointsDto(user_id=target.id, delta=Decimal("-10"), client_ip="127.0.0.1")
    )

    updated = await user_repository.find_by_id(target.id)
    assert updated.points == Decimal("20")


async def test_adjust_user_points_below_zero_raises_validation_error(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    async with uow:
        target = await _create_user(user_repository, 5005)
        await user_repository.credit_points(target.id, Decimal("10"))
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            AdjustUserPointsDto(user_id=target.id, delta=Decimal("-20"), client_ip="127.0.0.1"),
        )

    unchanged = await user_repository.find_by_id(target.id)
    assert unchanged.points == Decimal("10")


async def test_adjust_user_points_publishes_event(
    user_repository: UserRepository, uow, event_publisher, session
) -> None:
    target = await _create_user(user_repository, 5006)
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    await use_case(
        OWNER, AdjustUserPointsDto(user_id=target.id, delta=Decimal("15"), client_ip="127.0.0.1")
    )

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
    uow: UnitOfWork,
) -> None:
    use_case = GetReferralSettingsUseCase(
        referral_repository, PricingRepository(referral_repository.session), uow
    )
    regular_actor = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)

    with pytest.raises(PermissionDeniedError):
        await use_case(regular_actor)


async def test_update_referral_settings_persists_changes(
    referral_repository: ReferralRepository, uow, event_publisher
) -> None:
    use_case = UpdateReferralSettingsUseCase(
        referral_repository, PricingRepository(referral_repository.session), event_publisher, uow
    )

    result = await use_case(
        OWNER,
        UpdateReferralSettingsDto(
            enabled=True, max_level=2, reward_amounts={1: Decimal("5"), 2: Decimal("2")}
        ),
    )

    assert result.enabled is True
    assert result.max_level == 2
    assert result.anchor_currency is not None


async def test_update_referral_settings_rejects_a_percent_over_100(
    referral_repository: ReferralRepository, uow, event_publisher
) -> None:
    use_case = UpdateReferralSettingsUseCase(
        referral_repository, PricingRepository(referral_repository.session), event_publisher, uow
    )
    await use_case(OWNER, UpdateReferralSettingsDto(reward_amounts={1: Decimal("500")}))

    # switching strategy alone re-checks the amounts already stored
    with pytest.raises(ValidationError):
        await use_case(
            OWNER, UpdateReferralSettingsDto(reward_strategy=ReferralRewardStrategy.PERCENT)
        )

    result = await use_case(
        OWNER,
        UpdateReferralSettingsDto(
            reward_strategy=ReferralRewardStrategy.PERCENT, reward_amounts={1: Decimal("100")}
        ),
    )
    assert result.reward_strategy is ReferralRewardStrategy.PERCENT


async def test_get_own_referral_stats_reflects_referrer_and_counts(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    referrer = await _create_user(user_repository, 6001)
    a = await _create_user(user_repository, 6002)
    b = await _create_user(user_repository, 6003)
    await referral_repository.create_referral(referrer_id=referrer.id, referred_id=a.id, level=1)
    await referral_repository.create_referral(referrer_id=referrer.id, referred_id=b.id, level=1)
    use_case = GetOwnReferralStatsUseCase(referral_repository, user_repository, uow)

    stats = await use_case(referrer)

    assert stats.referral_code == referrer.referral_code
    assert stats.counts_by_level == {1: 2}
    assert stats.rewards == []


async def test_get_own_referral_stats_hides_a_staff_referrer(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    staff = await user_repository.create(
        CreateUserDto(name="staff", login="ref-staff", role=Role.ADMIN, telegram_id=6010)
    )
    invited = await _create_user(user_repository, 6011)
    await referral_repository.create_referral(referrer_id=staff.id, referred_id=invited.id, level=1)

    stats = await GetOwnReferralStatsUseCase(referral_repository, user_repository, uow)(invited)

    assert stats.referrer_id is None


async def test_get_own_referral_stats_includes_reward_history(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
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
        payment_key="order-1",
        type=ReferralRewardType.POINTS,
        amount=Decimal("7"),
    )
    use_case = GetOwnReferralStatsUseCase(referral_repository, user_repository, uow)

    stats = await use_case(referrer)

    assert len(stats.rewards) == 1
    assert stats.rewards[0].amount == Decimal("7")


async def test_get_user_referral_stats_requires_permission(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    target = await _create_user(user_repository, 6004)
    use_case = GetUserReferralStatsUseCase(referral_repository, user_repository, uow)
    regular_actor = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)

    with pytest.raises(PermissionDeniedError):
        await use_case(regular_actor, target.id)


async def test_get_user_referral_stats_includes_reward_history(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
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
        payment_key="order-1",
        type=ReferralRewardType.POINTS,
        amount=Decimal("9"),
    )
    use_case = GetUserReferralStatsUseCase(referral_repository, user_repository, uow)

    stats = await use_case(OWNER, referrer.id)

    assert len(stats.rewards) == 1
    assert stats.rewards[0].amount == Decimal("9")


async def test_get_user_referral_revenue_sums_downline_payments(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    root = await _create_user(user_repository, 6011)
    child = await _create_user(user_repository, 6012)
    grandchild = await _create_user(user_repository, 6013)
    outsider = await _create_user(user_repository, 6014)
    await referral_repository.create_referral(referrer_id=root.id, referred_id=child.id, level=1)
    await referral_repository.create_referral(
        referrer_id=child.id, referred_id=grandchild.id, level=2
    )
    for user, key, status in (
        (child, "rev-1", TransactionStatus.PAID),
        (grandchild, "rev-2", TransactionStatus.PAID),
        (grandchild, "rev-3", TransactionStatus.REFUNDED),
        (outsider, "rev-4", TransactionStatus.PAID),
    ):
        async with uow:
            order = await transaction_repository.create(
                _paid_order_dto(user_id=user.id, plan_id=plan_id, idempotency_key=key)
            )
        await transaction_repository.mark_status(order.id, status)
    use_case = GetUserReferralRevenueUseCase(
        referral_repository, user_repository, transaction_repository, pricing_repository, uow
    )

    revenue = await use_case(OWNER, root.id)

    rates = await pricing_repository.get_rate_table()
    assert revenue.currency == rates.anchor
    # two paid orders below root; the refund and the outsider don't count
    assert revenue.amount == 2 * convert_for_report(
        Decimal("500"), Currency.RUB, rates.anchor, rates
    )
    assert revenue.paying_count == 2

    revoked = OWNER.model_copy(update={"permission_revokes": ["REFERRALS_REVENUE_VIEW"]})
    with pytest.raises(PermissionDeniedError):
        await use_case(revoked, root.id)


def _paid_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreateTransactionDto:
    return CreateTransactionDto(
        channel=PurchaseChannel.CABINET,
        user_id=user_id,
        plan_id=plan_id,
        plan_snapshot=make_plan_snapshot(plan_id=plan_id),
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        target_subscription_id=None,
        gateway_type=PaymentGatewayType.YOOKASSA,
        base_price=Decimal("500"),
        discount_percent=0,
        discount_source=DiscountSource.NONE,
        final_price=Decimal("500"),
        anchor_base_price=Decimal("500"),
        anchor_final_price=Decimal("500"),
        customer_email=None,
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_list_referrals_requires_permission(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    use_case = ListReferralsUseCase(referral_repository, user_repository, uow)
    regular_actor = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)

    with pytest.raises(PermissionDeniedError):
        await use_case(regular_actor, ListReferralsDto())


async def test_list_referrals_joins_users_and_empty_rewards(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    referrer = await _create_user(user_repository, 5101)
    referred = await _create_user(user_repository, 5102)
    await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=referred.id, level=1
    )
    use_case = ListReferralsUseCase(referral_repository, user_repository, uow)

    items, total = await use_case(OWNER, ListReferralsDto())

    assert total == 1
    assert items[0].referred is not None and items[0].referred.id == referred.id
    assert items[0].referrer is not None and items[0].referrer.id == referrer.id
    assert items[0].rewards.count == 0
    assert items[0].rewards.amounts == {}


async def test_list_referrals_hides_staff_from_an_admin(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    referrer = await _create_user(user_repository, 5201)
    staff = await user_repository.create(
        CreateUserDto(name="staff", role=Role.ADMIN, telegram_id=5202)
    )
    await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=staff.id, level=1
    )
    use_case = ListReferralsUseCase(referral_repository, user_repository, uow)
    admin = UserDto(id=998, name="admin", role=Role.ADMIN, language=Locale.EN)

    items, _ = await use_case(admin, ListReferralsDto())
    assert items[0].referred is None and items[0].referrer is not None

    items, _ = await use_case(OWNER, ListReferralsDto())
    assert items[0].referred is not None


async def test_list_referrals_search_does_not_match_hidden_staff(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    referrer = await _create_user(user_repository, 5211)
    staff = await user_repository.create(
        CreateUserDto(name="staff", role=Role.ADMIN, telegram_id=5212, email="probe@example.com")
    )
    await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=staff.id, level=1
    )
    use_case = ListReferralsUseCase(referral_repository, user_repository, uow)
    admin = UserDto(id=998, name="admin", role=Role.ADMIN, language=Locale.EN)

    _, total = await use_case(admin, ListReferralsDto(search="probe@example"))
    assert total == 0

    _, total = await use_case(OWNER, ListReferralsDto(search="probe@example"))
    assert total == 1


async def test_list_invited_users_hides_staff_from_an_admin(
    referral_repository: ReferralRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    root = await _create_user(user_repository, 5221)
    staff = await user_repository.create(
        CreateUserDto(name="staff", role=Role.ADMIN, telegram_id=5222, email="probe2@example.com")
    )
    child = await _create_user(user_repository, 5223)
    await referral_repository.create_referral(referrer_id=root.id, referred_id=staff.id, level=1)
    await referral_repository.create_referral(referrer_id=staff.id, referred_id=child.id, level=2)
    use_case = ListInvitedUsersUseCase(referral_repository, user_repository, uow)
    admin = UserDto(id=998, name="admin", role=Role.ADMIN, language=Locale.EN)
    data = ListInvitedUsersDto(user_id=root.id)

    items, total = await use_case(admin, data)
    # hidden staff leave the list entirely; a customer they invited stays, without "via"
    assert [(i.depth, i.user.id if i.user else None) for i in items] == [(2, child.id)]
    assert total == 1
    assert items[0].via is None

    items, _ = await use_case(OWNER, data)
    by_depth = {i.depth: i for i in items}
    assert by_depth[1].user is not None and by_depth[2].via is not None

    _, total = await use_case(admin, ListInvitedUsersDto(user_id=root.id, search="probe2"))
    assert total == 0


async def test_get_user_referral_stats_hides_staff_from_an_admin(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
) -> None:
    staff_referrer = await user_repository.create(
        CreateUserDto(name="staff-ref", role=Role.ADMIN, telegram_id=5231)
    )
    target = await _create_user(user_repository, 5232)
    staff_buyer = await user_repository.create(
        CreateUserDto(name="staff-buyer", role=Role.ADMIN, telegram_id=5233)
    )
    await referral_repository.create_referral(
        referrer_id=staff_referrer.id, referred_id=target.id, level=1
    )
    edge = await referral_repository.create_referral(
        referrer_id=target.id, referred_id=staff_buyer.id, level=1
    )
    subscription_id = await _create_subscription(subscription_repository, staff_buyer.id, 5233)
    await referral_repository.create_reward(
        referral_id=edge.id,
        referrer_id=target.id,
        subscription_id=subscription_id,
        payment_key="order-staff",
        type=ReferralRewardType.POINTS,
        amount=Decimal("3"),
    )
    use_case = GetUserReferralStatsUseCase(referral_repository, user_repository, uow)
    admin = UserDto(id=998, name="admin", role=Role.ADMIN, language=Locale.EN)

    stats = await use_case(admin, target.id)
    # the staff buyer leaves the counts and the rewards, as it leaves the invited list
    assert stats.referrer is None
    assert stats.counts_by_level == {} and stats.rewards == []

    stats = await use_case(OWNER, target.id)
    assert stats.referrer is not None and stats.rewards[0].buyer is not None
    assert stats.counts_by_level == {1: 1}


async def test_reset_referral_code_issues_a_new_code_and_logs_it(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher,
    session: AsyncSession,
) -> None:
    user = await _create_user(user_repository, 6101)
    use_case = ResetReferralCodeUseCase(user_repository, uow, event_publisher)

    updated = await use_case(OWNER, user.id)

    assert updated.referral_code and updated.referral_code != user.referral_code
    assert await user_repository.find_by_referral_code(user.referral_code) is None
    rows = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == ReferralCodeResetEvent.__name__
            )
        )
    ).all()
    assert len(rows) == 1


async def test_reset_referral_code_unknown_user_raises(
    user_repository: UserRepository, uow: UnitOfWork, event_publisher
) -> None:
    with pytest.raises(NotFoundError):
        await ResetReferralCodeUseCase(user_repository, uow, event_publisher)(OWNER, 999_999)


async def test_reset_referral_settings_restores_defaults(
    referral_repository: ReferralRepository, uow: UnitOfWork, event_publisher
) -> None:
    pricing_repository = PricingRepository(referral_repository.session)
    await UpdateReferralSettingsUseCase(
        referral_repository, pricing_repository, event_publisher, uow
    )(
        OWNER,
        UpdateReferralSettingsDto(
            enabled=True,
            max_level=3,
            reward_strategy=ReferralRewardStrategy.PERCENT,
            reward_amounts={1: Decimal("10"), 2: Decimal("5"), 3: Decimal("1")},
        ),
    )

    result = await ResetReferralSettingsUseCase(
        referral_repository, pricing_repository, event_publisher, uow
    )(OWNER)

    assert result.enabled is False
    assert result.max_level == 1
    assert result.reward_strategy is ReferralRewardStrategy.AMOUNT
    assert (await referral_repository.get_settings()).max_level == 1


async def test_update_referral_settings_requires_a_reward_on_every_active_level(
    referral_repository: ReferralRepository, uow: UnitOfWork, event_publisher
) -> None:
    # unsaved actor: a rejected update rolls the seeded owner row back with it
    owner = OWNER.model_copy(update={"id": 0})
    use_case = UpdateReferralSettingsUseCase(
        referral_repository, PricingRepository(referral_repository.session), event_publisher, uow
    )

    with pytest.raises(ValidationError):
        await use_case(
            owner,
            UpdateReferralSettingsDto(
                enabled=True, max_level=2, reward_amounts={1: Decimal("5"), 2: Decimal("0")}
            ),
        )
    with pytest.raises(ValidationError):
        await use_case(owner, UpdateReferralSettingsDto(reward_amounts={1: Decimal("-1")}))

    # disabled: blanks are fine, levels past max_level are ignored
    await use_case(
        owner, UpdateReferralSettingsDto(enabled=False, reward_amounts={1: Decimal("0")})
    )
    result = await use_case(
        owner,
        UpdateReferralSettingsDto(
            enabled=True, max_level=1, reward_amounts={1: Decimal("5"), 2: Decimal("0")}
        ),
    )
    assert result.enabled is True


@pytest.mark.parametrize(
    ("reward_type", "amount"),
    [
        (ReferralRewardType.EXTRA_DAYS, Decimal(MAX_BONUS_DAYS + 1)),
        (ReferralRewardType.POINTS, Decimal(10**12)),
    ],
)
async def test_update_referral_settings_rejects_an_amount_reward_past_its_limit(
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
    event_publisher,
    reward_type: ReferralRewardType,
    amount: Decimal,
) -> None:
    owner = OWNER.model_copy(update={"id": 0})
    use_case = UpdateReferralSettingsUseCase(
        referral_repository, PricingRepository(referral_repository.session), event_publisher, uow
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            owner,
            UpdateReferralSettingsDto(
                reward_type=reward_type,
                reward_strategy=ReferralRewardStrategy.AMOUNT,
                reward_amounts={1: amount},
            ),
        )

    assert error.value.code is ErrorCode.REFERRAL_REWARD_TOO_HIGH


async def test_adjust_user_points_above_the_column_limit_raises_validation_error(
    user_repository: UserRepository, uow, event_publisher
) -> None:
    async with uow:
        target = await _create_user(user_repository, 5006)
        await user_repository.credit_points(target.id, Decimal(10**12 - 2))
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    with pytest.raises(ValidationError) as error:
        await use_case(
            OWNER, AdjustUserPointsDto(user_id=target.id, delta=Decimal("5"), client_ip="127.0.0.1")
        )

    assert error.value.code is ErrorCode.POINTS_LIMIT_EXCEEDED
    unchanged = await user_repository.find_by_id(target.id)
    assert unchanged.points == Decimal(10**12 - 2)


_PER_USER_CALLS = [
    "stats",
    "revenue",
    "invited",
    "adjust_points",
    "adjust_days",
    "reset_code",
]


def _per_user_call(name, referral_repository, user_repository, uow, event_publisher, session):  # type: ignore[no-untyped-def]
    def call(actor: UserDto, user_id: int):  # type: ignore[no-untyped-def]
        if name == "stats":
            return GetUserReferralStatsUseCase(referral_repository, user_repository, uow)(
                actor, user_id
            )
        if name == "revenue":
            return GetUserReferralRevenueUseCase(
                referral_repository,
                user_repository,
                TransactionRepository(session),
                PricingRepository(session),
                uow,
            )(actor, user_id)
        if name == "invited":
            return ListInvitedUsersUseCase(referral_repository, user_repository, uow)(
                actor, ListInvitedUsersDto(user_id=user_id)
            )
        if name == "adjust_points":
            return AdjustUserPointsUseCase(user_repository, uow, event_publisher)(
                actor,
                AdjustUserPointsDto(user_id=user_id, delta=Decimal("1"), client_ip="127.0.0.1"),
            )
        if name == "adjust_days":
            return AdjustUserBonusDaysUseCase(user_repository, uow, event_publisher)(
                actor, AdjustUserBonusDaysDto(user_id=user_id, delta=1, client_ip="127.0.0.1")
            )
        return ResetReferralCodeUseCase(user_repository, uow, event_publisher)(actor, user_id)

    return call


@pytest.mark.parametrize("name", _PER_USER_CALLS)
async def test_per_user_referral_routes_hide_staff_without_admins_manage(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher,
    session: AsyncSession,
    name: str,
) -> None:
    index = _PER_USER_CALLS.index(name)
    # committed: the refused call rolls its own transaction back
    async with uow:
        staff = await user_repository.create(
            CreateUserDto(name="staff", role=Role.ADMIN, telegram_id=6200 + index)
        )
        # an admin with default permissions: no ADMINS_MANAGE
        admin = await user_repository.create(
            CreateUserDto(name="plain-admin", role=Role.ADMIN, telegram_id=6300 + index)
        )
    call = _per_user_call(name, referral_repository, user_repository, uow, event_publisher, session)

    with pytest.raises(NotFoundError) as error:
        await call(admin, staff.id)

    assert error.value.code is ErrorCode.USER_NOT_FOUND
    unchanged = await user_repository.find_by_id(staff.id)
    assert unchanged is not None and unchanged.referral_code == staff.referral_code
    await call(OWNER, staff.id)


async def test_get_user_referral_revenue_leaves_out_hidden_staff(
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    root = await _create_user(user_repository, 6021)
    child = await _create_user(user_repository, 6022)
    staff = await user_repository.create(
        CreateUserDto(name="staff", role=Role.ADMIN, telegram_id=6023)
    )
    for referred in (child, staff):
        await referral_repository.create_referral(
            referrer_id=root.id, referred_id=referred.id, level=1
        )
    for user, key in ((child, "rev-staff-1"), (staff, "rev-staff-2")):
        async with uow:
            order = await transaction_repository.create(
                _paid_order_dto(user_id=user.id, plan_id=plan_id, idempotency_key=key)
            )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    use_case = GetUserReferralRevenueUseCase(
        referral_repository, user_repository, transaction_repository, pricing_repository, uow
    )
    admin = UserDto(id=998, name="admin", role=Role.ADMIN, language=Locale.EN)

    assert (await use_case(admin, root.id)).paying_count == 1
    assert (await use_case(OWNER, root.id)).paying_count == 2


async def test_adjust_user_points_skips_an_anonymized_account(
    user_repository: UserRepository, uow, event_publisher, session: AsyncSession
) -> None:
    target = await _create_user(user_repository, 5010)
    await session.execute(
        update(User).where(User.id == target.id).values(deleted_at=datetime_now())
    )
    use_case = AdjustUserPointsUseCase(user_repository, uow, event_publisher)

    with pytest.raises(NotFoundError):
        await use_case(
            OWNER,
            AdjustUserPointsDto(user_id=target.id, delta=Decimal("10"), client_ip="127.0.0.1"),
        )


async def _set_referral_reset(
    settings_repository: SettingsRepository, uow: UnitOfWork, *, enabled: bool, hours: int
) -> None:
    async with uow:
        await settings_repository.update_shop_settings(
            UpdateShopSettingsDto(
                referral_reset_enabled=enabled,
                referral_reset_cooldown_hours=hours,
                fields_set=frozenset({"referral_reset_enabled", "referral_reset_cooldown_hours"}),
            )
        )


async def test_own_referral_code_reset_waits_out_its_cooldown(
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher,
) -> None:
    await _set_referral_reset(settings_repository, uow, enabled=True, hours=24)
    user = await _create_user(user_repository, 6201)
    use_case = ResetOwnReferralCodeUseCase(
        user_repository, settings_repository, uow, event_publisher
    )

    updated = await use_case(user)

    assert updated.referral_code and updated.referral_code != user.referral_code
    with pytest.raises(CooldownError):
        await use_case(updated)


async def test_own_referral_code_reset_can_be_turned_off(
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    event_publisher,
) -> None:
    await _set_referral_reset(settings_repository, uow, enabled=False, hours=0)
    user = await _create_user(user_repository, 6202)
    use_case = ResetOwnReferralCodeUseCase(
        user_repository, settings_repository, uow, event_publisher
    )

    with pytest.raises(ValidationError):
        await use_case(user)
