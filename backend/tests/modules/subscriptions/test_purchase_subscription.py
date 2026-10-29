import asyncio
import contextlib
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

import httpx
import pytest
from remnapy import RemnawaveSDK
from remnapy.enums import TrafficLimitStrategy
from remnapy.models import UpdateUserRequestDto
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core.db.models import (
    EventOutboxEntry,
    Plan,
    Subscription,
    SubscriptionPurchaseIdempotency,
    Transaction,
    User,
)
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AddOnType,
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PlanType,
    PurchaseChannel,
    PurchaseType,
    Role,
    RoundingMode,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.error_codes import ErrorCode
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
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    GrantAddOnDto,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.panel import restore
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    FulfillPurchaseUseCase,
    GrantAddOnUseCase,
    PurchaseSubscriptionUseCase,
)
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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


async def test_a_paid_renew_takes_the_plans_tag_and_a_bonus_one_keeps_it(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 412)
    plan = await _create_plan(plan_repository, "renew-tag")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
        UserRepository(subscription_repository.session),
    )
    snapshot = snapshot_from_plan(
        plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
    )

    def order(purchase_type: PurchaseType, **overrides: Any) -> PurchaseSubscriptionDto:
        fields: dict[str, Any] = {
            "user_id": buyer.id,
            "plan_snapshot": snapshot,
            "duration_days": 30,
            "price_paid": Decimal("299.00"),
            "currency": Currency.RUB,
            "purchase_type": purchase_type,
        }
        return PurchaseSubscriptionDto(**(fields | overrides))

    original = await use_case(buyer, order(PurchaseType.NEW))
    paid = await use_case(
        buyer,
        order(
            PurchaseType.RENEW,
            plan_snapshot=replace(snapshot, tag="VIP"),
            target_subscription_id=original.id,
            apply_plan_tag=True,
        ),
    )
    bonus = await use_case(buyer, order(PurchaseType.RENEW, target_subscription_id=original.id))

    panel_user = await remnawave_sdk.users.get_user_by_id(original.remnawave_user_id)
    assert (paid.tag, bonus.tag, panel_user.tag) == ("VIP", "VIP", "VIP")


async def test_a_paid_renew_lands_even_when_the_panel_refuses_the_tag(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _create_buyer(user_repository, 413)
    plan = await _create_plan(plan_repository, "renew-tag-refused")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
        UserRepository(subscription_repository.session),
    )
    snapshot = snapshot_from_plan(
        plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
    )
    common: dict[str, Any] = {
        "user_id": buyer.id,
        "duration_days": 30,
        "price_paid": Decimal("299.00"),
        "currency": Currency.RUB,
    }
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(**common, plan_snapshot=snapshot, purchase_type=PurchaseType.NEW),
    )
    update_user = remnawave_sdk.users.update_user

    async def refuse_tag(request: UpdateUserRequestDto) -> Any:
        if "tag" in request.model_fields_set:
            raise RuntimeError("panel refused the tag")
        return await update_user(request)

    monkeypatch.setattr(remnawave_sdk.users, "update_user", refuse_tag)

    renewed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            **common,
            plan_snapshot=replace(snapshot, tag="VIP"),
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=original.id,
            apply_plan_tag=True,
        ),
    )

    assert renewed.expire_at == original.expire_at + timedelta(days=30)
    # the row doesn't claim a tag the panel never took
    assert renewed.tag is None


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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
    # base_price stays None, as for non-checkout callers: the denominator
    # falls back to price_paid

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

    # CHANGE makes a new row on the same panel user; the old row stays as
    # DELETED history
    assert changed.id != old_subscription.id
    assert changed.remnawave_user_id == old_subscription.remnawave_user_id
    assert changed.status.value == "ACTIVE"
    assert changed.plan_snapshot.plan_id == new_plan.id

    stored = await subscription_repository.list_all()
    assert len(stored) == 2

    old_after = await subscription_repository.get_by_id(old_subscription.id)
    assert old_after.status.value == "DELETED"

    expected_days = 30 + 30  # duration_days + credit_days
    # both the credit's (old_expire_at - now).days and this assertion's
    # (expire_at - now).days floor, so up to 2 days can go
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
        UserRepository(subscription_repository.session),
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
    # so the credit buys 30 days, not 300 / 0.1 = 3000.
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
        UserRepository(subscription_repository.session),
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
    # buy 60, twice what the user is owed.
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
    # a denominator discounted along with the price lands at ~90 days
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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

    assert changed.id != trial_subscription.id
    assert changed.remnawave_user_id == trial_subscription.remnawave_user_id
    assert changed.status.value == "ACTIVE"
    assert changed.plan_snapshot.plan_id == new_plan.id

    stored = await subscription_repository.list_all()
    assert len(stored) == 2

    old_after = await subscription_repository.get_by_id(trial_subscription.id)
    assert old_after.status.value == "DELETED"

    # no credit: expire_at is now + 30 days
    assert (changed.expire_at - datetime_now()).days in (29, 30)


class _NoopEventPublisher:
    async def publish(self, event: object) -> None:
        return None


async def test_concurrent_new_purchases_never_exceed_the_cap(
    engine: AsyncEngine,
    remnawave_sdk: RemnawaveSDK,
) -> None:
    # N concurrent purchases for one user stop at exactly the cap (the
    # ShopSettingsDto default, 3), the rest raise ValidationError. Separate
    # connections, since an AsyncSession can't run concurrently, so the seed
    # rows are committed and cleaned up by hand.
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
            UserRepository(repo.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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


async def test_cancelled_purchase_releases_its_idempotency_key(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 405)
    plan = await _create_plan(plan_repository, "cancel-test")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
        UserRepository(subscription_repository.session),
    )

    async def _cancelled(*args: object, **kwargs: object) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(use_case._new, "run", _cancelled)

    with pytest.raises(asyncio.CancelledError):
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
                idempotency_key="cancel-key-1",
            ),
        )

    assert (
        await idempotency_repository.session.get(SubscriptionPurchaseIdempotency, "cancel-key-1")
        is None
    )


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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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

    # the entitlement stays on the old, now DELETED row
    old_after = await subscription_repository.get_by_id(old_subscription.id)
    assert old_after.status.value == "DELETED"
    assert len(old_after.addon_entitlements) == 1
    assert old_after.addon_entitlements[0].addon_id == addon.id

    # the new row has only the new plan's limits
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
    # same panel user and URL
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
        UserRepository(subscription_repository.session),
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
    linked = await idempotency_repository.find_subscription_id(renewal.idempotency_key)
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
        UserRepository(subscription_repository.session),
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

    updated = await user_repository.find_by_id(buyer.id)
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
        UserRepository(subscription_repository.session),
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


async def test_change_that_loses_the_race_gives_the_panel_back_to_the_winner(
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
        UserRepository(subscription_repository.session),
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
    winner: list[SubscriptionDto] = []

    async def update_while_a_concurrent_change_commits(dto: object) -> object:
        update_calls.append(dto)
        if len(update_calls) == 1:
            # the competing CHANGE commits between this panel call and the row lock,
            # its own row taking over the same panel user
            async with uow:
                await subscription_repository.mark_deleted(old_subscription.id)
                winner.append(
                    await subscription_repository.create(
                        CreateSubscriptionDto(
                            user_id=buyer.id,
                            remnawave_user_id=old_subscription.remnawave_user_id,
                            status=SubscriptionStatus.ACTIVE,
                            traffic_limit=777,
                            device_limit=7,
                            expire_at=old_subscription.expire_at + timedelta(days=90),
                            url=old_subscription.url,
                            plan_snapshot=make_plan_snapshot(),
                        )
                    )
                )
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

    # the loser's config is undone with the winner's, not its own stale one
    assert update_calls[1:] == [restore(winner[0])]


async def _disabled_subscription(
    use_case: PurchaseSubscriptionUseCase,
    subscription_repository: SubscriptionRepository,
    buyer: UserDto,
    plan: PlanDto,
) -> int:
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
    await subscription_repository.session.execute(
        update(Subscription)
        .where(Subscription.id == original.id)
        .values(status=SubscriptionStatus.DISABLED)
    )
    return original.id


def _renewal(buyer: UserDto, plan: PlanDto, target_id: int) -> PurchaseSubscriptionDto:
    return PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
        ),
        duration_days=30,
        price_paid=Decimal("299.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=target_id,
    )


async def test_renew_refuses_a_disabled_target(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
) -> None:
    buyer = await _create_buyer(user_repository, 431)
    plan = await _create_plan(plan_repository, "renew-disabled")
    target_id = await _disabled_subscription(
        purchase_subscription_use_case, subscription_repository, buyer, plan
    )

    with pytest.raises(ValidationError) as error:
        await purchase_subscription_use_case(buyer, _renewal(buyer, plan, target_id))

    assert error.value.code is ErrorCode.SUBSCRIPTION_DISABLED


async def test_a_paid_order_still_renews_a_subscription_disabled_after_checkout(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
) -> None:
    buyer = await _create_buyer(user_repository, 432)
    plan = await _create_plan(plan_repository, "renew-disabled-paid")
    target_id = await _disabled_subscription(
        purchase_subscription_use_case, subscription_repository, buyer, plan
    )
    fulfill = FulfillPurchaseUseCase(
        user_repository,
        purchase_subscription_use_case,
        TransactionRepository(user_repository.session),
        UnitOfWork(user_repository.session),
    )

    renewed = await fulfill.system(_renewal(buyer, plan, target_id))

    assert renewed is not None
    assert renewed.id == target_id


def _purchase_use_case(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> PurchaseSubscriptionUseCase:
    return PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
        UserRepository(subscription_repository.session),
    )


async def test_new_purchase_without_publish_event_writes_no_outbox_row(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 9101)
    plan = await _create_plan(plan_repository, "silent")
    use_case = _purchase_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )

    await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(plan),
            duration_days=30,
            price_paid=Decimal(0),
            currency=Currency.USD,
            purchase_type=PurchaseType.NEW,
            publish_event=False,
        ),
    )

    rows = (
        await subscription_repository.session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "SubscriptionPurchasedEvent"
            )
        )
    ).all()
    assert rows == []


async def test_change_with_keep_expire_at_keeps_the_old_expiry(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 9102)
    first_plan = await _create_plan(plan_repository, "first")
    second_plan = await _create_plan(plan_repository, "second")
    use_case = _purchase_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    old = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(first_plan, duration_days=45),
            duration_days=45,
            price_paid=Decimal(0),
            currency=Currency.USD,
            purchase_type=PurchaseType.NEW,
        ),
    )

    changed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(second_plan, duration_days=45),
            duration_days=45,
            price_paid=Decimal(0),
            currency=Currency.USD,
            purchase_type=PurchaseType.CHANGE,
            target_subscription_id=old.id,
            keep_expire_at=True,
            publish_event=False,
        ),
    )

    assert changed.expire_at == old.expire_at
    assert changed.plan_snapshot.plan_id == second_plan.id
    assert changed.remnawave_user_id == old.remnawave_user_id
    rows = (
        await subscription_repository.session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "SubscriptionChangedEvent"
            )
        )
    ).all()
    assert rows == []


@pytest.mark.parametrize("reset_traffic", [True, False])
async def test_change_deducts_spent_traffic_from_the_credit(
    reset_traffic: bool,
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
    buyer = await _create_buyer(user_repository, 450)
    old_plan = await _create_plan(plan_repository, "spent-old")
    new_plan = await _create_plan(plan_repository, "spent-new")
    use_case = PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
        UserRepository(subscription_repository.session),
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
    spent = 95 * 1024**3  # of 100 GB
    remnawave_store[old_subscription.remnawave_user_id]["userTraffic"]["usedTrafficBytes"] = spent

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
            reset_traffic=reset_traffic,
        ),
    )

    # 5% of the traffic left caps the credit at 15 => 1 day at 10/day,
    # instead of the 30 days the untouched term alone would give
    assert (changed.expire_at - datetime_now()).days in (29, 30)
    used = remnawave_store[changed.remnawave_user_id]["userTraffic"]["usedTrafficBytes"]
    assert used == (0 if reset_traffic else spent)


async def test_change_credit_is_the_average_rate_over_renewals(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 431)
    plan = await _create_plan(plan_repository, "cumcredit")
    use_case = _purchase_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )

    def dto(
        days: int, price: str, purchase_type: PurchaseType, target: Optional[int] = None
    ) -> PurchaseSubscriptionDto:
        return PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal(price), currency=Currency.RUB, duration_days=days
            ),
            duration_days=days,
            price_paid=Decimal(price),
            base_price=Decimal(price),
            currency=Currency.RUB,
            purchase_type=purchase_type,
            target_subscription_id=target,
        )

    original = await use_case(buyer, dto(30, "100", PurchaseType.NEW))
    renewed = await use_case(buyer, dto(365, "600", PurchaseType.RENEW, original.id))

    assert renewed.plan_snapshot.credit_paid == Decimal("700")
    assert renewed.plan_snapshot.credit_days == 395
    assert renewed.plan_snapshot.price_paid == Decimal("100")
    assert renewed.plan_snapshot.duration_days == 30

    changed = await use_case(buyer, dto(365, "600", PurchaseType.CHANGE, renewed.id))

    # 700 credit at 600/365 per day is about 426 days
    days = (changed.expire_at - datetime_now()).days
    assert 365 + 426 - 4 <= days <= 365 + 426 + 1


async def test_a_free_renewal_adds_days_to_the_credit_but_not_money(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 432)
    plan = await _create_plan(plan_repository, "freecredit")
    use_case = _purchase_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    snapshot = snapshot_from_plan(
        plan, price_paid=Decimal("100"), currency=Currency.RUB, duration_days=30
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot,
            duration_days=30,
            price_paid=Decimal("100"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    granted = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=replace(snapshot, price_paid=Decimal("0")),
            duration_days=30,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=original.id,
        ),
    )

    assert granted.plan_snapshot.credit_paid == Decimal("100")
    assert granted.plan_snapshot.credit_days == 60


async def test_a_renewal_in_another_currency_accumulates_in_the_snapshot_currency(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    pricing_repository: PricingRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> None:
    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("100"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    buyer = await _create_buyer(user_repository, 433)
    plan = await _create_plan(plan_repository, "fxcredit")
    use_case = _purchase_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    original = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("300"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    # 3 USD at RUB=100 is 300 RUB
    renewed = await use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("3"), currency=Currency.USD, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("3"),
            currency=Currency.USD,
            purchase_type=PurchaseType.RENEW,
            target_subscription_id=original.id,
        ),
    )

    assert renewed.plan_snapshot.currency is Currency.RUB
    assert renewed.plan_snapshot.credit_paid == Decimal("600")
    assert renewed.plan_snapshot.credit_days == 60


def _trial_dto(buyer: UserDto, plan: PlanDto) -> PurchaseSubscriptionDto:
    return PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("0"), currency=Currency.RUB, duration_days=3, is_trial=True
        ),
        duration_days=3,
        price_paid=Decimal("0"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
    )


def _paid_new_dto(
    buyer: UserDto, plan: PlanDto, *, reset_traffic: bool = False
) -> PurchaseSubscriptionDto:
    return PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("299.00"), currency=Currency.RUB, duration_days=30
        ),
        duration_days=30,
        price_paid=Decimal("299.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        reset_traffic=reset_traffic,
    )


async def test_a_paid_upgrade_enables_a_disabled_trial(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_store: FakeUserStore,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
) -> None:
    buyer = await _create_buyer(user_repository, 9201)
    trial_plan = await _create_plan(plan_repository, "disabled-trial")
    paid_plan = await _create_plan(plan_repository, "disabled-trial-paid")
    trial = await purchase_subscription_use_case(buyer, _trial_dto(buyer, trial_plan))
    remnawave_store[trial.remnawave_user_id]["status"] = "DISABLED"
    await subscription_repository.session.execute(
        update(Subscription)
        .where(Subscription.id == trial.id)
        .values(status=SubscriptionStatus.DISABLED)
    )

    paid = await purchase_subscription_use_case(buyer, _paid_new_dto(buyer, paid_plan))

    assert paid.remnawave_user_id == trial.remnawave_user_id
    assert paid.status is SubscriptionStatus.ACTIVE
    assert remnawave_store[trial.remnawave_user_id]["status"] == "ACTIVE"


async def test_a_paid_purchase_replaces_an_expired_trial_and_keeps_its_link(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_store: FakeUserStore,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
) -> None:
    buyer = await _create_buyer(user_repository, 9202)
    trial_plan = await _create_plan(plan_repository, "expired-trial")
    paid_plan = await _create_plan(plan_repository, "expired-trial-paid")
    trial = await purchase_subscription_use_case(buyer, _trial_dto(buyer, trial_plan))
    remnawave_store[trial.remnawave_user_id]["status"] = "EXPIRED"
    await subscription_repository.session.execute(
        update(Subscription)
        .where(Subscription.id == trial.id)
        .values(status=SubscriptionStatus.EXPIRED)
    )

    paid = await purchase_subscription_use_case(buyer, _paid_new_dto(buyer, paid_plan))

    assert paid.remnawave_user_id == trial.remnawave_user_id
    assert paid.url == trial.url
    assert paid.status is SubscriptionStatus.ACTIVE
    assert len(remnawave_store) == 1
    assert (await subscription_repository.get_by_id(trial.id)).status is (
        SubscriptionStatus.DELETED
    )


async def test_a_paid_upgrade_of_a_trial_resets_its_traffic(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    monkeypatch: pytest.MonkeyPatch,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
) -> None:
    buyer = await _create_buyer(user_repository, 9202)
    trial_plan = await _create_plan(plan_repository, "reset-trial")
    paid_plan = await _create_plan(plan_repository, "reset-trial-paid")
    trial = await purchase_subscription_use_case(buyer, _trial_dto(buyer, trial_plan))
    resets: list[object] = []
    original_reset = remnawave_sdk.users.reset_user_traffic

    async def counting_reset(user_id: object) -> object:
        resets.append(user_id)
        return await original_reset(user_id)  # type: ignore[arg-type]

    monkeypatch.setattr(remnawave_sdk.users, "reset_user_traffic", counting_reset)

    await purchase_subscription_use_case(buyer, _paid_new_dto(buyer, paid_plan, reset_traffic=True))

    assert resets == [trial.remnawave_user_id]


async def test_a_change_racing_a_renewal_credits_the_renewed_days(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    monkeypatch: pytest.MonkeyPatch,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
) -> None:
    buyer = await _create_buyer(user_repository, 9203)
    old_plan = await _create_plan(plan_repository, "race-renew-old")
    new_plan = await _create_plan(plan_repository, "race-renew-new")

    def dto(
        plan: PlanDto, purchase_type: PurchaseType, target: Optional[int] = None
    ) -> PurchaseSubscriptionDto:
        return PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("300"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300"),
            base_price=Decimal("300"),
            currency=Currency.RUB,
            purchase_type=purchase_type,
            target_subscription_id=target,
        )

    old = await purchase_subscription_use_case(buyer, dto(old_plan, PurchaseType.NEW))
    reached, release = asyncio.Event(), asyncio.Event()
    original_get = remnawave_sdk.users.get_user_by_id
    gated = False

    async def gated_get(user_id: object) -> object:
        # first call is CHANGE's credit read, right after its unlocked row read
        nonlocal gated
        if not gated:
            gated = True
            reached.set()
            await release.wait()
        return await original_get(user_id)  # type: ignore[arg-type]

    monkeypatch.setattr(remnawave_sdk.users, "get_user_by_id", gated_get)

    change = asyncio.create_task(
        purchase_subscription_use_case(buyer, dto(new_plan, PurchaseType.CHANGE, old.id))
    )
    await reached.wait()
    await purchase_subscription_use_case(buyer, dto(old_plan, PurchaseType.RENEW, old.id))
    release.set()
    changed = await change

    # 600 paid over 60 days left, at 10/day: about 60 credit days on top of 30
    # (the stale read gave about 30)
    assert 88 <= (changed.expire_at - datetime_now()).days <= 90


async def test_a_second_change_credits_back_the_credit_the_first_one_carried(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
) -> None:
    buyer = await _create_buyer(user_repository, 9204)
    plan = await _create_plan(plan_repository, "double-change")

    def dto(
        days: int, price: str, purchase_type: PurchaseType, target: Optional[int] = None
    ) -> PurchaseSubscriptionDto:
        return PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal(price), currency=Currency.RUB, duration_days=days
            ),
            duration_days=days,
            price_paid=Decimal(price),
            base_price=Decimal(price),
            currency=Currency.RUB,
            purchase_type=purchase_type,
            target_subscription_id=target,
        )

    original = await purchase_subscription_use_case(buyer, dto(365, "600", PurchaseType.NEW))
    first = await purchase_subscription_use_case(
        buyer, dto(30, "100", PurchaseType.CHANGE, original.id)
    )
    # about 598 credit at 100/30 per day: 179 days on top of 30
    assert first.plan_snapshot.credit_days == 30 + 179
    assert Decimal("698") < first.plan_snapshot.effective_credit_paid < Decimal("699")

    second = await purchase_subscription_use_case(
        buyer, dto(30, "100", PurchaseType.CHANGE, first.id)
    )

    # about 695 credit carried, not capped at the second order's 100 (30 days)
    assert 30 + 205 <= (second.expire_at - datetime_now()).days <= 30 + 209


async def test_a_change_outrun_by_renewals_twice_gives_up_and_restores_the_panel(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    monkeypatch: pytest.MonkeyPatch,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
) -> None:
    buyer = await _create_buyer(user_repository, 9205)
    old_plan = await _create_plan(plan_repository, "race-twice-old")
    new_plan = await _create_plan(plan_repository, "race-twice-new")

    def dto(
        plan: PlanDto, purchase_type: PurchaseType, target: Optional[int] = None
    ) -> PurchaseSubscriptionDto:
        return PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(
                plan, price_paid=Decimal("300"), currency=Currency.RUB, duration_days=30
            ),
            duration_days=30,
            price_paid=Decimal("300"),
            base_price=Decimal("300"),
            currency=Currency.RUB,
            purchase_type=purchase_type,
            target_subscription_id=target,
        )

    old = await purchase_subscription_use_case(buyer, dto(old_plan, PurchaseType.NEW))
    reached, release = asyncio.Event(), asyncio.Event()
    original_get = remnawave_sdk.users.get_user_by_id
    gated = 0

    async def gated_get(user_id: object) -> object:
        # each attempt's credit read, right after its unlocked row read
        nonlocal gated
        if gated < 2:
            gated += 1
            reached.set()
            await release.wait()
            release.clear()
        return await original_get(user_id)  # type: ignore[arg-type]

    monkeypatch.setattr(remnawave_sdk.users, "get_user_by_id", gated_get)

    change = asyncio.create_task(
        purchase_subscription_use_case(buyer, dto(new_plan, PurchaseType.CHANGE, old.id))
    )
    for _ in range(2):
        await reached.wait()
        reached.clear()
        await purchase_subscription_use_case(buyer, dto(old_plan, PurchaseType.RENEW, old.id))
        release.set()

    with pytest.raises(ValidationError) as raised:
        await change

    assert raised.value.code is ErrorCode.PURCHASE_SUPERSEDED
    current = await subscription_repository.get_by_id(old.id)
    panel_expire = remnawave_store[old.remnawave_user_id]["expireAt"]
    assert datetime.fromisoformat(panel_expire.replace("Z", "+00:00")) == current.expire_at


async def _capped_buyer_with_open_order(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    telegram_id: int,
    order_key: str,
) -> tuple[UserDto, PlanDto]:
    buyer = await _create_buyer(user_repository, telegram_id)
    plan = await _create_plan(plan_repository, f"open-{telegram_id}")
    await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=1, fields_set=frozenset({"max_active_subscriptions"})
        )
    )
    await TransactionRepository(plan_repository.session).create(
        CreateTransactionDto(
            channel=PurchaseChannel.CABINET,
            user_id=buyer.id,
            plan_id=plan.id,
            plan_snapshot=snapshot_from_plan(plan),
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
            gateway_type=PaymentGatewayType.YOOKASSA,
            base_price=Decimal("0"),
            discount_percent=0,
            discount_source=DiscountSource.NONE,
            final_price=Decimal("0"),
            anchor_base_price=Decimal("0"),
            anchor_final_price=Decimal("0"),
            customer_email=None,
            idempotency_key=order_key,
            expires_at=datetime_now() + timedelta(minutes=30),
        )
    )
    return buyer, plan


@pytest.mark.parametrize(("key", "refused"), [("own-free-order", False), (None, True)])
async def test_new_purchase_counts_other_open_orders_but_not_its_own(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    key: Optional[str],
    refused: bool,
) -> None:
    buyer, plan = await _capped_buyer_with_open_order(
        plan_repository, user_repository, settings_repository, 430, "own-free-order"
    )
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(plan),
        duration_days=30,
        price_paid=Decimal("0"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        idempotency_key=key,
    )

    if refused:
        with pytest.raises(ValidationError) as error:
            await purchase_subscription_use_case(buyer, dto)
        assert error.value.code is ErrorCode.SUBSCRIPTION_LIMIT_REACHED
    else:
        await purchase_subscription_use_case(buyer, dto)


async def test_trial_is_not_crowded_out_by_an_open_order(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    buyer, plan = await _capped_buyer_with_open_order(
        plan_repository, user_repository, settings_repository, 431, "paid-later"
    )

    await purchase_subscription_use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(plan, is_trial=True),
            duration_days=3,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    assert len(await subscription_repository.get_active_by_user(buyer.id)) == 1


async def test_a_reclaimed_new_attempt_returns_the_finished_subscription(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _create_buyer(user_repository, 432)
    plan = await _create_plan(plan_repository, "reclaim-test")
    dto = PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
        ),
        duration_days=30,
        price_paid=Decimal("100.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        idempotency_key="reclaimed-key",
    )
    first = await purchase_subscription_use_case(buyer, dto)
    disabled: list[object] = []
    original_disable = remnawave_sdk.users.disable_user

    async def _tracking_disable(user_id: object) -> None:
        disabled.append(user_id)
        await original_disable(user_id)

    monkeypatch.setattr(remnawave_sdk.users, "disable_user", _tracking_disable)

    # a stalled attempt resumes after the attempt that reclaimed its key finished
    again = await purchase_subscription_use_case._new.run(buyer, dto)

    assert again.id == first.id
    assert len(await subscription_repository.get_active_by_user(buyer.id)) == 1
    assert len(disabled) == 1


async def test_releasing_a_key_keeps_it_once_a_subscription_is_linked(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    idempotency_repository: PurchaseIdempotencyRepository,
    uow: UnitOfWork,
) -> None:
    buyer = await _create_buyer(user_repository, 433)
    plan = await _create_plan(plan_repository, "release-test")
    finished = await purchase_subscription_use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(plan),
            duration_days=30,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            idempotency_key="linked-key",
        ),
    )

    # a reclaiming attempt that fails afterwards must not erase the finished one's link
    async with uow:
        await idempotency_repository.release("linked-key", datetime_now())

    assert await idempotency_repository.find_subscription_id("linked-key") == finished.id


async def test_a_trial_activated_mid_purchase_is_retired_by_the_paid_subscription(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _create_buyer(user_repository, 434)
    plan = await _create_plan(plan_repository, "late-trial")
    real_create = remnawave_sdk.users.create_user
    trials: list[SubscriptionDto] = []

    async def _create_then_trial(request: object) -> object:
        created = await real_create(request)
        if not trials:
            # a trial activation that commits while this purchase is in flight
            trials.append(
                await subscription_repository.create(
                    CreateSubscriptionDto(
                        user_id=buyer.id,
                        remnawave_user_id=987_434,
                        status=SubscriptionStatus.ACTIVE,
                        is_trial=True,
                        traffic_limit=100,
                        device_limit=3,
                        expire_at=datetime_now() + timedelta(days=3),
                        url="https://example.com/sub/987434",
                        plan_snapshot=make_plan_snapshot(is_trial=True),
                    )
                )
            )
        return created

    disabled: list[object] = []
    real_disable = remnawave_sdk.users.disable_user

    async def _tracking_disable(user_id: object) -> None:
        disabled.append(user_id)
        with contextlib.suppress(Exception):
            await real_disable(user_id)

    monkeypatch.setattr(remnawave_sdk.users, "create_user", _create_then_trial)
    monkeypatch.setattr(remnawave_sdk.users, "disable_user", _tracking_disable)

    paid = await purchase_subscription_use_case(
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
            enforce_subscription_cap=False,
        ),
    )

    active = await subscription_repository.get_active_by_user(buyer.id)
    assert [s.id for s in active] == [paid.id]
    assert (await subscription_repository.get_by_id(trials[0].id)).status is (
        SubscriptionStatus.DELETED
    )
    assert disabled == [987_434]


async def test_a_late_trial_does_not_count_against_a_free_orders_cap(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buyer = await _create_buyer(user_repository, 435)
    plan = await _create_plan(plan_repository, "late-trial-free")
    await settings_repository.update_shop_settings(
        UpdateShopSettingsDto(
            max_active_subscriptions=1, fields_set=frozenset({"max_active_subscriptions"})
        )
    )
    real_create = remnawave_sdk.users.create_user

    async def _create_then_trial(request: object) -> object:
        created = await real_create(request)
        await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=buyer.id,
                remnawave_user_id=987_435,
                status=SubscriptionStatus.ACTIVE,
                is_trial=True,
                traffic_limit=100,
                device_limit=3,
                expire_at=datetime_now() + timedelta(days=3),
                url="https://example.com/sub/987435",
                plan_snapshot=make_plan_snapshot(is_trial=True),
            )
        )
        return created

    monkeypatch.setattr(remnawave_sdk.users, "create_user", _create_then_trial)

    paid = await purchase_subscription_use_case(
        buyer,
        PurchaseSubscriptionDto(
            user_id=buyer.id,
            plan_snapshot=snapshot_from_plan(plan),
            duration_days=30,
            price_paid=Decimal("0"),
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
        ),
    )

    active = await subscription_repository.get_active_by_user(buyer.id)
    assert [s.id for s in active] == [paid.id]


def _purchase_use_case(
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    idempotency_repository: PurchaseIdempotencyRepository,
) -> PurchaseSubscriptionUseCase:
    return PurchaseSubscriptionUseCase(
        subscription_repository,
        make_eligibility(subscription_repository.session),
        remnawave_sdk,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
        PricingRepository(subscription_repository.session),
        idempotency_repository,
        UserRepository(subscription_repository.session),
    )


def _buy(
    user: UserDto,
    plan: PlanDto,
    *,
    is_trial: bool = False,
    target_subscription_id: Optional[int] = None,
) -> PurchaseSubscriptionDto:
    price = Decimal(0) if is_trial else Decimal("300.00")
    days = 3 if is_trial else 30
    return PurchaseSubscriptionDto(
        user_id=user.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=price, currency=Currency.RUB, duration_days=days, is_trial=is_trial
        ),
        duration_days=days,
        price_paid=price,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW if target_subscription_id is None else PurchaseType.CHANGE,
        target_subscription_id=target_subscription_id,
    )


async def test_a_trial_upgrade_that_loses_the_race_gives_the_panel_back_to_the_winner(
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
    buyer = await _create_buyer(user_repository, 4401)
    use_case = _purchase_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    trial_plan = await _create_plan(plan_repository, "race-trial")
    paid_plan = await _create_plan(plan_repository, "race-trial-paid")
    trial = await use_case(buyer, _buy(buyer, trial_plan, is_trial=True))

    update_calls: list[object] = []
    original_update = remnawave_sdk.users.update_user
    winner: list[SubscriptionDto] = []

    async def update_while_another_upgrade_commits(dto: object) -> object:
        update_calls.append(dto)
        if len(update_calls) == 1:
            async with uow:
                await subscription_repository.mark_deleted(trial.id)
                winner.append(
                    await subscription_repository.create(
                        CreateSubscriptionDto(
                            user_id=buyer.id,
                            remnawave_user_id=trial.remnawave_user_id,
                            status=SubscriptionStatus.ACTIVE,
                            traffic_limit=777,
                            device_limit=7,
                            expire_at=trial.expire_at + timedelta(days=60),
                            url=trial.url,
                            plan_snapshot=make_plan_snapshot(),
                        )
                    )
                )
        return await original_update(dto)  # type: ignore[arg-type]

    monkeypatch.setattr(remnawave_sdk.users, "update_user", update_while_another_upgrade_commits)

    with pytest.raises(ValidationError):
        await use_case(buyer, _buy(buyer, paid_plan))

    assert update_calls[1:] == [restore(winner[0])]


async def test_a_trial_upgrade_redoes_its_panel_config_over_an_addon_pushed_meanwhile(
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
    buyer = await _create_buyer(user_repository, 4402)
    use_case = _purchase_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    trial_plan = await _create_plan(plan_repository, "addon-trial")
    paid_plan = await _create_plan(plan_repository, "addon-trial-paid")
    trial = await use_case(buyer, _buy(buyer, trial_plan, is_trial=True))

    update_calls: list[object] = []
    original_update = remnawave_sdk.users.update_user

    async def update_while_an_addon_is_granted(dto: object) -> object:
        update_calls.append(dto)
        if len(update_calls) == 1:
            # a promocode's addon lands on the trial and pushes its own limits
            async with uow:
                await subscription_repository.grant_entitlement(
                    subscription_id=trial.id, addon_id=None, addon_type=AddOnType.TRAFFIC, amount=5
                )
        return await original_update(dto)  # type: ignore[arg-type]

    monkeypatch.setattr(remnawave_sdk.users, "update_user", update_while_an_addon_is_granted)

    await use_case(buyer, _buy(buyer, paid_plan))

    # the plan's config is pushed again under the lock, over the addon's
    assert len(update_calls) == 2
    assert update_calls[1] == update_calls[0]


async def test_a_change_retries_over_an_addon_pushed_meanwhile(
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
    buyer = await _create_buyer(user_repository, 4403)
    use_case = _purchase_use_case(
        subscription_repository, remnawave_sdk, uow, event_publisher, idempotency_repository
    )
    old_plan = await _create_plan(plan_repository, "addon-change-old")
    new_plan = await _create_plan(plan_repository, "addon-change-new")
    old = await use_case(buyer, _buy(buyer, old_plan))

    update_calls: list[object] = []
    original_update = remnawave_sdk.users.update_user

    async def update_while_an_addon_is_granted(dto: object) -> object:
        update_calls.append(dto)
        if len(update_calls) == 1:
            async with uow:
                await subscription_repository.grant_entitlement(
                    subscription_id=old.id, addon_id=None, addon_type=AddOnType.TRAFFIC, amount=5
                )
        return await original_update(dto)  # type: ignore[arg-type]

    monkeypatch.setattr(remnawave_sdk.users, "update_user", update_while_an_addon_is_granted)

    changed = await use_case(
        buyer,
        _buy(buyer, new_plan, target_subscription_id=old.id),
    )

    assert changed.plan_snapshot.plan_id == new_plan.id
    # first attempt saw the addon under the lock and went again: its config is the last word
    assert len(update_calls) == 2


async def _paid_order(
    session: AsyncSession,
    buyer: UserDto,
    plan: PlanDto,
    key: str,
    *,
    purchase_type: PurchaseType = PurchaseType.NEW,
    target_subscription_id: Optional[int] = None,
    status: TransactionStatus = TransactionStatus.PAID,
) -> None:
    repository = TransactionRepository(session)
    order = await repository.create(
        CreateTransactionDto(
            channel=PurchaseChannel.CABINET,
            user_id=buyer.id,
            plan_id=plan.id,
            plan_snapshot=snapshot_from_plan(plan),
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=purchase_type,
            target_subscription_id=target_subscription_id,
            gateway_type=PaymentGatewayType.YOOKASSA,
            base_price=Decimal("100.00"),
            discount_percent=0,
            discount_source=DiscountSource.NONE,
            final_price=Decimal("100.00"),
            anchor_base_price=Decimal("100.00"),
            anchor_final_price=Decimal("100.00"),
            customer_email=None,
            idempotency_key=key,
            expires_at=datetime_now() + timedelta(minutes=30),
        )
    )
    await repository.mark_status(order.id, status)


async def _refund(session: AsyncSession, key: str) -> None:
    await session.execute(
        update(Transaction)
        .where(Transaction.idempotency_key == key)
        .values(status=TransactionStatus.REFUNDED)
    )


def _paid_purchase(
    buyer: UserDto,
    plan: PlanDto,
    key: str,
    purchase_type: PurchaseType = PurchaseType.NEW,
    target_subscription_id: Optional[int] = None,
) -> PurchaseSubscriptionDto:
    return PurchaseSubscriptionDto(
        user_id=buyer.id,
        plan_snapshot=snapshot_from_plan(
            plan, price_paid=Decimal("100.00"), currency=Currency.RUB, duration_days=30
        ),
        duration_days=30,
        price_paid=Decimal("100.00"),
        currency=Currency.RUB,
        purchase_type=purchase_type,
        target_subscription_id=target_subscription_id,
        idempotency_key=key,
    )


async def test_a_refunded_order_is_not_provisioned(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_store: FakeUserStore,
) -> None:
    buyer = await _create_buyer(user_repository, 440)
    plan = await _create_plan(plan_repository, "refunded-before")
    await _paid_order(
        plan_repository.session, buyer, plan, "refunded-before", status=TransactionStatus.REFUNDED
    )

    with pytest.raises(ValidationError) as error:
        await purchase_subscription_use_case(buyer, _paid_purchase(buyer, plan, "refunded-before"))

    assert error.value.code is ErrorCode.PAYMENT_ORDER_NOT_FULFILLABLE
    assert remnawave_store == {}
    assert await subscription_repository.get_active_by_user(buyer.id) == []


async def test_an_order_refunded_mid_purchase_disables_the_new_panel_user(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = plan_repository.session
    buyer = await _create_buyer(user_repository, 441)
    plan = await _create_plan(plan_repository, "refunded-mid-new")
    await _paid_order(session, buyer, plan, "refunded-mid-new")
    create_user = remnawave_sdk.users.create_user

    async def create_then_refund(*args, **kwargs):  # type: ignore[no-untyped-def]
        created = await create_user(*args, **kwargs)
        await _refund(session, "refunded-mid-new")
        return created

    monkeypatch.setattr(remnawave_sdk.users, "create_user", create_then_refund)

    with pytest.raises(ValidationError) as error:
        await purchase_subscription_use_case(buyer, _paid_purchase(buyer, plan, "refunded-mid-new"))

    assert error.value.code is ErrorCode.PAYMENT_ORDER_NOT_FULFILLABLE
    (panel_user,) = remnawave_store.values()
    assert panel_user["status"] == "DISABLED"
    assert await subscription_repository.get_active_by_user(buyer.id) == []


async def test_an_order_refunded_mid_renewal_takes_the_extension_back(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = plan_repository.session
    buyer = await _create_buyer(user_repository, 442)
    plan = await _create_plan(plan_repository, "refunded-mid-renew")
    target = await purchase_subscription_use_case(
        buyer, replace(_paid_purchase(buyer, plan, "unused"), idempotency_key=None)
    )
    await _paid_order(
        session,
        buyer,
        plan,
        "refunded-mid-renew",
        purchase_type=PurchaseType.RENEW,
        target_subscription_id=target.id,
    )
    update_user = remnawave_sdk.users.update_user
    refunded: list[bool] = []

    async def update_then_refund(*args, **kwargs):  # type: ignore[no-untyped-def]
        updated = await update_user(*args, **kwargs)
        if not refunded:
            refunded.append(True)
            await _refund(session, "refunded-mid-renew")
        return updated

    monkeypatch.setattr(remnawave_sdk.users, "update_user", update_then_refund)

    with pytest.raises(ValidationError) as error:
        await purchase_subscription_use_case(
            buyer,
            _paid_purchase(
                buyer,
                plan,
                "refunded-mid-renew",
                PurchaseType.RENEW,
                target_subscription_id=target.id,
            ),
        )

    assert error.value.code is ErrorCode.PAYMENT_ORDER_NOT_FULFILLABLE
    current = await subscription_repository.get_by_id(target.id)
    assert current.expire_at == target.expire_at
    panel_expire = remnawave_store[target.remnawave_user_id]["expireAt"]
    assert datetime.fromisoformat(panel_expire.replace("Z", "+00:00")) == target.expire_at


async def test_fulfilling_a_refunded_order_ends_without_a_retry(
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
) -> None:
    buyer = await _create_buyer(user_repository, 443)
    plan = await _create_plan(plan_repository, "refunded-fulfill")
    await _paid_order(
        plan_repository.session, buyer, plan, "refunded-fulfill", status=TransactionStatus.REFUNDED
    )
    fulfill = FulfillPurchaseUseCase(
        user_repository,
        purchase_subscription_use_case,
        TransactionRepository(user_repository.session),
        UnitOfWork(user_repository.session),
    )

    assert await fulfill.system(_paid_purchase(buyer, plan, "refunded-fulfill")) is None
    assert await subscription_repository.get_active_by_user(buyer.id) == []
