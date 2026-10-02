import asyncio
import contextlib
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from remnapy import RemnawaveSDK
from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core.db.models import EventOutboxEntry, Plan, Subscription, User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AddOnType,
    Currency,
    PlanType,
    PurchaseType,
    Role,
    RoundingMode,
    SubscriptionStatus,
)
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    CreateAddOnDto,
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing.dto import UpdateCurrencyRateDto
from app.modules.pricing.repository import PricingRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    GrantAddOnDto,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import GrantAddOnUseCase, PurchaseSubscriptionUseCase
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore
from tests.modules.subscriptions.factories import (
    make_eligibility,
    make_plan_snapshot,
    snapshot_from_plan,
)


async def _create_buyer(user_repository: UserRepository, telegram_id: int) -> UserDto:
    return await user_repository.create(CreateUserDto(name="buyer", telegram_id=telegram_id))


async def _create_plan(plan_repository: PlanRepository, public_code: str = "basic") -> PlanDto:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code=public_code,
            name=public_code,
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


async def test_new_purchase_creates_subscription_with_real_remnawave_identity(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 401)
    plan = await _create_plan(plan_repository)
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
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
    assert subscription.plan_snapshot.plan_id == plan.id
    assert subscription.plan_snapshot.price_paid == Decimal("299.00")
    assert subscription.plan_snapshot.duration_days == 30

    stored = await subscription_repository.list_all()
    assert len(stored) == 1


async def test_new_purchase_forbidden_for_a_different_users_actor(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 402)
    other_actor = await _create_buyer(user_repository, 403)
    plan = await _create_plan(plan_repository, "basic2")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            other_actor,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot_from_plan(
                    plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
                ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 404)
    # A real row, not the module-level OWNER dto: event_outbox.actor_id is a
    # real FK into users and this use case publishes with the actor attached.
    owner = (await _create_buyer(user_repository, 4040)).model_copy(
        update={"role": Role.OWNER, "login": "owner"}
    )
    plan = await _create_plan(plan_repository, "basic3")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    subscription = await use_case(
        owner,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 405)
    plan = await _create_plan(plan_repository, "basic4")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot_from_plan(
                    plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
                ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 406)
    plan = await _create_plan(plan_repository, "basic5")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
        ),
        duration_days=30,
        price_paid=Decimal("299.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
    )

    for _ in range(3):
        await use_case(buyer, dto)

    with pytest.raises(ValidationError):
        await use_case(buyer, dto)


async def test_new_purchase_at_the_cap_never_touches_the_panel(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 408)
    plan = await _create_plan(plan_repository, "capnopanel")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
        ),
        duration_days=30,
        price_paid=Decimal("299.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
    )
    for _ in range(3):
        await use_case(buyer, dto)
    panel_users_before = len(remnawave_store)

    with pytest.raises(ValidationError):
        await use_case(buyer, dto)

    assert len(remnawave_store) == panel_users_before


async def test_renew_extends_expire_at_and_calls_remnawave_extend(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 411)
    plan = await _create_plan(plan_repository, "renew1")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
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
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 412)
    plan = await _create_plan(plan_repository, "renew2")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot_from_plan(
                    plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
                ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 413)
    other_buyer = await _create_buyer(user_repository, 414)
    plan = await _create_plan(plan_repository, "renew3")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    other_subscription = await use_case(
        other_buyer,
        PurchaseSubscriptionDto(
            user_id=other_buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
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
                plan_snapshot=snapshot_from_plan(
                    plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
                ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 415)
    plan_a = await _create_plan(plan_repository, "renew4a")
    plan_b = await _create_plan(plan_repository, "renew4b")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan_a, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
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
                plan_snapshot=snapshot_from_plan(
                    plan_b, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
                ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 424)
    plan = await _create_plan(plan_repository, "renew5")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
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
                plan_snapshot=snapshot_from_plan(
                    plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
                ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 421)
    old_plan = await _create_plan(plan_repository, "change1old")
    new_plan = await _create_plan(plan_repository, "change1new")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    old_subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                old_plan, price_paid=Decimal("300.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    # Full 30 days remaining, price_paid=300/30days => daily_rate=10 => full
    # credit=300 => at new plan's daily_rate=10 (300/30) => 30 credit-days.
    # base_price is left at its None default here -- the non-checkout callers'
    # path, where the denominator falls back to price_paid.

    changed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                new_plan, price_paid=Decimal("300.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=old_subscription.id,
        ),
    )

    # CHANGE now creates a new row sharing the old one's panel identity --
    # the old row is kept as DELETED history, not mutated.
    assert changed.id != old_subscription.id
    assert changed.remnawave_user_id == old_subscription.remnawave_user_id
    assert changed.status.value == "ACTIVE"
    assert changed.plan_snapshot.plan_id == new_plan.id

    stored = await subscription_repository.list_all()
    assert len(stored) == 2

    old_after = await subscription_repository.get_by_id(old_subscription.id)
    assert old_after.status.value == "DELETED"

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


async def test_change_converts_proration_credit_across_currencies(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    pricing_repository: PricingRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    await pricing_repository.get_rate_table()  # seeds the rate rows
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("100"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    buyer = await _create_buyer(user_repository, 427)
    old_plan = await _create_plan(plan_repository, "changefxold")
    new_plan = await _create_plan(plan_repository, "changefxnew")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        pricing_repository,
        idempotency_repository,
    )
    old_subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                old_plan, price_paid=Decimal("300"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    # 300 RUB of credit at RUB=100 is 3 USD; the new plan costs 3 USD / 30 days,
    # so the credit buys 30 days -- not 300 / 0.1 = 3000.
    changed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                new_plan, price_paid=Decimal("3.00"), currency=Currency.USD, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("3.00"),
            base_price=Decimal("3.00"),
            currency=Currency.USD,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=old_subscription.id,
        ),
    )

    expected_days = 30 + 30
    assert (changed.expire_at - datetime_now()).days in (
        expected_days - 2,
        expected_days - 1,
        expected_days,
    )


async def test_change_credit_converts_at_list_price_not_the_discounted_price(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 428)
    old_plan = await _create_plan(plan_repository, "change-discount-old")
    new_plan = await _create_plan(plan_repository, "change-discount-new")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    old_subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                old_plan, price_paid=Decimal("300.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    # 50%-off promo: list price 300 over 30d => daily rate 10 => credit 300
    # buys 30 days at list rate. At the discounted 150/30d = 5/day it would
    # buy 60 -- twice what the user is owed.
    changed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                new_plan, price_paid=Decimal("150.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("150.00"),
            base_price=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=old_subscription.id,
        ),
    )

    # CHANGE now creates a new row sharing the old one's panel identity --
    # the old row is kept as DELETED history, not mutated.
    assert changed.id != old_subscription.id
    assert changed.remnawave_user_id == old_subscription.remnawave_user_id
    assert changed.status.value == "ACTIVE"
    assert changed.plan_snapshot.plan_id == new_plan.id

    stored = await subscription_repository.list_all()
    assert len(stored) == 2

    old_after = await subscription_repository.get_by_id(old_subscription.id)
    assert old_after.status.value == "DELETED"

    expected_days = 30 + 30
    assert (changed.expire_at - datetime_now()).days in (
        expected_days - 2,
        expected_days - 1,
        expected_days,
    )
    # The discounted-denominator bug would land at ~90 days.
    assert (changed.expire_at - datetime_now()).days < 70


async def test_change_requires_target_subscription_id(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 422)
    plan = await _create_plan(plan_repository, "change2")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot_from_plan(
                    plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
                ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
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
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=trial_plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=trial_plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    trial_plan = await plan_repository.update(UpdatePlanDto(plan_id=trial_plan.id, is_active=True))
    new_plan = await _create_plan(plan_repository, "change3new")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    trial_subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                trial_plan, price_paid=Decimal("0"), currency=Currency.RUB, duration_days=7
            ),
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
            plan_snapshot=snapshot_from_plan(
                new_plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=trial_subscription.id,
        ),
    )

    # CHANGE now creates a new row sharing the old one's panel identity --
    # the old row is kept as DELETED history, not mutated.
    assert changed.id != trial_subscription.id
    assert changed.remnawave_user_id == trial_subscription.remnawave_user_id
    assert changed.status.value == "ACTIVE"
    assert changed.plan_snapshot.plan_id == new_plan.id

    stored = await subscription_repository.list_all()
    assert len(stored) == 2

    old_after = await subscription_repository.get_by_id(trial_subscription.id)
    assert old_after.status.value == "DELETED"

    # No credit -- expire_at is just now + 30 days, no bonus days.
    assert (changed.expire_at - datetime_now()).days in (29, 30)


class _NoopEventPublisher:
    async def publish(self, event: object) -> None:
        return None


async def test_concurrent_new_purchases_never_exceed_the_cap(
    engine: AsyncEngine,
    remnawave_sdk: RemnawaveSDK,
) -> None:
    # The isolated lock test proves acquire_purchase_cap_lock serializes; this
    # proves the end-to-end property -- N genuinely concurrent
    # PurchaseSubscriptionUseCase calls for one user settle at exactly the
    # cap, the rest ValidationError. No shop_settings row is ever written in
    # this test, so the cap is ShopSettingsDto's own default (3) -- needs
    # independent connections (AsyncSession forbids concurrent use), the seed
    # rows committed for real, and explicit cleanup since committed rows
    # bypass the rollback-per-test fixture.
    test_cap = 3
    attempts = test_cap + 3
    buyer_id = 0
    plan_id = 0

    async def one_purchase(conn: AsyncConnection, buyer: UserDto, plan_id: int) -> str:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        repo = SubscriptionRepository(session)
        use_case = PurchaseSubscriptionUseCase(
            repo,
            make_eligibility(repo.session),
            remnawave_sdk,
            UnitOfWork(session),
            _NoopEventPublisher(),
            SubscriptionLifecycleService(repo),
            PricingRepository(session),
            PurchaseIdempotencyRepository(session),
        )
        try:
            await use_case(
                buyer,
                PurchaseSubscriptionDto(
                    user_id=buyer.id,
                    plan_snapshot=make_plan_snapshot(
                        plan_id=plan_id, price_paid=Decimal(0), currency=Currency.USD
                    ),
                    duration_days=30,
                    price_paid=Decimal(0),
                    currency=Currency.USD,
                    purchase_type=PurchaseType.NEW,
                ),
            )
            return "ok"
        except ValidationError:
            return "rejected"
        finally:
            await session.close()

    try:
        async with contextlib.AsyncExitStack() as stack:
            conns = [await stack.enter_async_context(engine.connect()) for _ in range(attempts + 1)]

            setup = AsyncSession(bind=conns[0], expire_on_commit=False)
            buyer = await UserRepository(setup).create(
                CreateUserDto(name="cap-buyer", telegram_id=90210)
            )
            plan = await PlanRepository(setup).create(
                CreatePlanDto(
                    public_code="cap-race",
                    name="cap-race",
                    type=PlanType.BOTH,
                    traffic_limit=100,
                    device_limit=3,
                )
            )
            await PlanRepository(setup).set_durations(
                SetPlanDurationsDto(
                    plan_id=plan.id,
                    durations=[
                        SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))
                    ],
                )
            )
            await PlanRepository(setup).update_squads(
                UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
            )
            await PlanRepository(setup).update(UpdatePlanDto(plan_id=plan.id, is_active=True))
            await setup.commit()
            await setup.close()
            buyer_id, plan_id = buyer.id, plan.id

            results = await asyncio.gather(
                *(one_purchase(conns[i + 1], buyer, plan_id) for i in range(attempts))
            )
            assert results.count("ok") == test_cap
            assert results.count("rejected") == attempts - test_cap

            check = AsyncSession(bind=conns[0], expire_on_commit=False)
            active = await SubscriptionRepository(check).get_active_by_user(buyer_id)
            assert len(active) == test_cap
            await check.close()
    finally:
        # Delete by the seed's natural keys, not the captured ids: a killed run
        # never binds buyer_id/plan_id and would leak the rows into the next run.
        async with engine.begin() as cleanup:
            await cleanup.execute(
                delete(Subscription).where(
                    Subscription.user_id.in_(select(User.id).where(User.telegram_id == 90210))
                )
            )
            await cleanup.execute(delete(Plan).where(Plan.public_code == "cap-race"))
            await cleanup.execute(delete(User).where(User.telegram_id == 90210))


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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 403)
    plan = await _create_plan(plan_repository, "idem-test")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
        ),
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


async def test_purchase_failure_after_panel_call_disables_the_panel_user(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 404)
    plan = await _create_plan(plan_repository, "compensate-test")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    disabled_ids: list[int] = []
    original_disable = remnawave_sdk.users.disable_user

    async def _tracking_disable(user_id: int) -> None:
        disabled_ids.append(user_id)
        await original_disable(user_id)

    monkeypatch.setattr(remnawave_sdk.users, "disable_user", _tracking_disable)

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(subscription_repository, "create", _boom)

    with pytest.raises(RuntimeError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot_from_plan(
                    plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
                ),
                duration_days=30,
                price_paid=Decimal("100.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
            ),
        )

    assert len(disabled_ids) == 1


async def test_renew_reactivates_an_expired_subscription(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 405)
    plan = await _create_plan(plan_repository, "renew-test")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    purchased = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
            ),
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
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
            ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 407)
    plan = await _create_plan(plan_repository, "idem-renew-test")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    purchased = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("100.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    renew_dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
        ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 408)
    plan = await _create_plan(plan_repository, "idem-retry-test")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
        ),
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
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 409)
    plan = await _create_plan(plan_repository, "idem-panel-fail-test")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
        ),
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


async def test_change_does_not_reparent_addon_entitlement_to_the_new_row(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 440)
    old_plan = await _create_plan(plan_repository, "reparent-old")
    new_plan = await _create_plan(plan_repository, "reparent-new")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    old_subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                old_plan, price_paid=Decimal("300.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="reparent-traffic-addon",
            type=AddOnType.TRAFFIC,
            amount=50,
            base_price=Decimal("1.99"),
        )
    )
    grant_use_case = GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )
    await grant_use_case.system(
        GrantAddOnDto(subscription_id=old_subscription.id, addon_id=addon.id)
    )

    changed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                new_plan, price_paid=Decimal("300.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=old_subscription.id,
        ),
    )

    # The entitlement stays on the OLD (now DELETED) row -- never reparented.
    old_after = await subscription_repository.get_by_id(old_subscription.id)
    assert old_after.status.value == "DELETED"
    assert len(old_after.addon_entitlements) == 1
    assert old_after.addon_entitlements[0].addon_id == addon.id

    # The NEW row carries no bonus -- just the new plan's own base limits.
    assert changed.addon_entitlements == []
    assert changed.effective_traffic_limit == new_plan.traffic_limit
    assert changed.effective_device_limit == new_plan.device_limit


async def test_trial_upgrade_does_not_reparent_addon_entitlement_to_the_new_row(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    addon_repository: AddOnRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 441)
    trial_plan = await _create_plan(plan_repository, "reparent-trial-trial")
    paid_plan = await _create_plan(plan_repository, "reparent-trial-paid")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    trial = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                trial_plan,
                price_paid=Decimal("0"),
                currency=Currency.RUB,
                duration_days=3,
                is_trial=True,
            ),
            duration_days=3,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    addon = await addon_repository.create(
        CreateAddOnDto(
            name="reparent-trial-devices-addon",
            type=AddOnType.DEVICES,
            amount=2,
            base_price=Decimal("0.99"),
        )
    )
    grant_use_case = GrantAddOnUseCase(
        subscription_repository,
        addon_repository,
        user_repository,
        remnawave_sdk,
        uow,
        event_publisher,
    )
    await grant_use_case.system(GrantAddOnDto(subscription_id=trial.id, addon_id=addon.id))

    paid = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                paid_plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    old_trial = await subscription_repository.get_by_id(trial.id)
    assert old_trial.status.value == "DELETED"
    assert len(old_trial.addon_entitlements) == 1
    assert old_trial.addon_entitlements[0].addon_id == addon.id

    assert paid.addon_entitlements == []
    assert paid.effective_traffic_limit == paid_plan.traffic_limit
    assert paid.effective_device_limit == paid_plan.device_limit


async def test_new_purchase_upgrades_an_active_trial_in_place(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 501)
    trial_plan = await _create_plan(plan_repository, "trial-upgrade-trial")
    paid_plan = await _create_plan(plan_repository, "trial-upgrade-paid")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    trial = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                trial_plan,
                price_paid=Decimal("0"),
                currency=Currency.RUB,
                duration_days=3,
                is_trial=True,
            ),
            duration_days=3,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    assert trial.is_trial is True

    paid = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                paid_plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    # New row, not a mutation of the trial's.
    assert paid.id != trial.id
    # Same panel identity/URL -- the whole point.
    assert paid.remnawave_user_id == trial.remnawave_user_id
    assert paid.url == trial.url
    assert paid.is_trial is False

    old_trial = await subscription_repository.get_by_id(trial.id)
    assert old_trial.status.value == "DELETED"

    stored = await subscription_repository.list_all()
    assert len(stored) == 2


async def test_new_purchase_without_a_trial_still_mints_a_fresh_panel_user(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 502)
    plan = await _create_plan(plan_repository, "no-trial-new")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    assert subscription.remnawave_user_id > 0
    stored = await subscription_repository.list_all()
    assert len(stored) == 1


async def test_new_purchase_provisions_the_plans_traffic_limit_strategy_on_the_panel(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # create_user defaults trafficLimitStrategy to NO_RESET, so omitting it
    # silently provisions a never-resetting panel user for a MONTH plan while
    # the local row (and the dashboard) claim MONTH.
    buyer = await _create_buyer(user_repository, 431)
    plan = await _create_plan(plan_repository, "monthly-reset")
    plan = await plan_repository.update(
        UpdatePlanDto(plan_id=plan.id, traffic_limit_strategy=TrafficLimitStrategy.MONTH)
    )
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )

    subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    panel_user = await remnawave_sdk.users.get_user_by_id(subscription.remnawave_user_id)
    assert panel_user.traffic_limit_strategy is TrafficLimitStrategy.MONTH
    assert subscription.traffic_limit_strategy is TrafficLimitStrategy.MONTH


def _to_ms(value: datetime) -> datetime:
    # the real panel stores milliseconds; the fake keeps whatever it was given
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


async def _renew_fixture(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    *,
    telegram_id: int,
    public_code: str,
) -> tuple[
    PurchaseSubscriptionUseCase,
    SubscriptionLifecycleService,
    UserDto,
    SubscriptionDto,
    PurchaseSubscriptionDto,
]:
    buyer = await _create_buyer(user_repository, telegram_id)
    plan = await _create_plan(plan_repository, public_code)
    lifecycle = SubscriptionLifecycleService(subscription_repository)
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        lifecycle,
        PricingRepository(subscription_repository.session),
        PurchaseIdempotencyRepository(subscription_repository.session),
    )
    snapshot = snapshot_from_plan(
        plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot,
            duration_days=30,
            price_paid=Decimal("299.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )
    renewal = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot,
        duration_days=30,
        price_paid=Decimal("299.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=original.id,
        idempotency_key=uuid4().hex,
    )
    return use_case, lifecycle, buyer, original, renewal


async def test_a_renew_whose_db_write_failed_is_completed_by_the_retry_without_extending_twice(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    use_case, lifecycle, buyer, original, renewal = await _renew_fixture(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        telegram_id=432,
        public_code="renew-retry",
    )
    before = (await remnawave_sdk.users.get_user_by_id(original.remnawave_user_id)).expire_at

    real_renew = lifecycle.renew

    async def _fail(*_args: object, **_kwargs: object) -> SubscriptionDto:
        raise RuntimeError("DB write failed after the panel call landed")

    lifecycle.renew = _fail  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await use_case(buyer, renewal)
    after_first = (await remnawave_sdk.users.get_user_by_id(original.remnawave_user_id)).expire_at
    assert after_first == _to_ms(before + timedelta(days=30))

    lifecycle.renew = real_renew  # type: ignore[method-assign]
    renewed = await use_case(buyer, renewal)

    after_retry = (await remnawave_sdk.users.get_user_by_id(original.remnawave_user_id)).expire_at
    assert after_retry == after_first
    assert renewed.expire_at == after_first
    assert renewal.idempotency_key is not None
    linked = await idempotency_repository.get_subscription_id(renewal.idempotency_key)
    assert linked == original.id
    # a third delivery is a plain replay of the finished purchase
    assert (await use_case(buyer, renewal)).id == original.id


async def test_a_renew_whose_panel_response_was_lost_is_not_applied_twice(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_case, _, buyer, original, renewal = await _renew_fixture(
        plan_repository,
        subscription_repository,
        user_repository,
        settings_repository,
        remnawave_sdk,
        uow,
        event_publisher,
        telegram_id=434,
        public_code="renew-lost-response",
    )
    before = (await remnawave_sdk.users.get_user_by_id(original.remnawave_user_id)).expire_at

    real_update = remnawave_sdk.users.update_user

    async def _landed_then_lost(*args: object, **kwargs: object) -> object:
        await real_update(*args, **kwargs)  # type: ignore[arg-type]
        raise httpx.ReadTimeout("response lost after the panel applied the write")

    monkeypatch.setattr(remnawave_sdk.users, "update_user", _landed_then_lost)
    with pytest.raises(httpx.ReadTimeout):
        await use_case(buyer, renewal)
    monkeypatch.setattr(remnawave_sdk.users, "update_user", real_update)

    renewed = await use_case(buyer, renewal)

    after = (await remnawave_sdk.users.get_user_by_id(original.remnawave_user_id)).expire_at
    assert after == _to_ms(before + timedelta(days=30))
    assert renewed.expire_at == after


async def test_a_system_grant_does_not_consume_the_purchase_discount(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # A trial / promocode reward / referral EXTRA_DAYS grant never quoted a
    # price, so it must not burn a discount the customer never got to use.
    buyer = await _create_buyer(user_repository, 433)
    plan = await _create_plan(plan_repository, "granted-free")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    async with uow:
        await user_repository.update_fields(buyer.id, UpdateUserDto(purchase_discount=15))

    await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("0"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    updated = await user_repository.get_by_id(buyer.id)
    assert updated is not None
    assert updated.purchase_discount == 15


async def test_only_a_paid_purchase_event_carries_the_payment_key(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    # referrals rewards key off payment_key: a paid order has one, a
    # trial/promocode/referral grant does not
    buyer = await _create_buyer(user_repository, 435)
    plan = await _create_plan(plan_repository, "payment-key")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        PurchaseIdempotencyRepository(subscription_repository.session),
    )
    snapshot = snapshot_from_plan(
        plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
    )
    for key in ("paid-order-key", None):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot,
                duration_days=30,
                price_paid=Decimal("299.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                idempotency_key=key,
            ),
        )

    rows = (
        await session.scalars(
            select(EventOutboxEntry)
            .where(EventOutboxEntry.event_type == "SubscriptionPurchasedEvent")
            .order_by(EventOutboxEntry.id)
        )
    ).all()
    assert [row.payload["payment_key"] for row in rows] == ["paid-order-key", None]


async def test_change_that_loses_the_race_does_not_revert_the_winners_panel_config(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 431)
    old_plan = await _create_plan(plan_repository, "racelostold")
    new_plan = await _create_plan(plan_repository, "racelostnew")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
    )
    old_subscription = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                old_plan, price_paid=Decimal("300.00"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300.00"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    update_calls: list[object] = []
    original_update = remnawave_sdk.users.update_user

    async def update_while_a_concurrent_change_commits(dto: object) -> object:
        update_calls.append(dto)
        if len(update_calls) == 1:
            # the competing CHANGE commits between this panel call and the row lock
            await subscription_repository.mark_deleted(old_subscription.id)
        return await original_update(dto)  # type: ignore[arg-type]

    monkeypatch.setattr(
        remnawave_sdk.users, "update_user", update_while_a_concurrent_change_commits
    )

    with pytest.raises(ValidationError):
        await use_case(
            buyer,
            PurchaseSubscriptionDto(
                user_id=buyer.id,
                plan_snapshot=snapshot_from_plan(
                    new_plan, price_paid=Decimal("300.00"), currency=Currency.RUB, duration_days=30
                ),
                duration_days=30,
                price_paid=Decimal("300.00"),
                currency=Currency.RUB,
                purchase_type=PurchaseType.CHANGE,
                target_subscription_id=old_subscription.id,
            ),
        )

    assert len(update_calls) == 1  # no compensating revert onto the winner's identity
