from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from remnapy import RemnawaveSDK

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PlanType, PurchaseType
from app.core.ports import EventPublisher
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
from app.modules.subscriptions.dto import PurchaseSubscriptionDto, SubscriptionDto
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
