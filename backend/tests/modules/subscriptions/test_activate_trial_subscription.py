from decimal import Decimal
from uuid import uuid4

import pytest
from remnapy import RemnawaveSDK
from sqlalchemy import select

from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import PlanType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.modules.plans.dto import (
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    ActivateTrialSubscriptionUseCase,
    PurchaseSubscriptionUseCase,
)
from app.modules.users.dto import CreateUserDto, UpdateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_eligibility


async def _create_trial_plan(plan_repository: PlanRepository, price: str = "0"):
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="activate-trial",
            name="Trial",
            type=PlanType.BOTH,
            traffic_limit=10,
            device_limit=1,
            is_trial=True,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=3, order_index=0, base_price=Decimal(price))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    return await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))


async def test_activates_a_trial_and_spends_the_flag(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await _create_trial_plan(plan_repository)
    actor = await user_repository.create(CreateUserDto(name="trial-activator"))
    purchase_use_case = PurchaseSubscriptionUseCase(
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
    use_case = ActivateTrialSubscriptionUseCase(
        user_repository,
        plan_repository,
        PricingRepository(subscription_repository.session),
        make_eligibility(subscription_repository.session),
        purchase_use_case,
        uow,
    )

    subscription = await use_case(actor)

    assert subscription.is_trial is True
    assert subscription.plan_snapshot.price_paid == Decimal("0")

    reloaded = await user_repository.find_by_id(actor.id)
    assert reloaded.is_trial_available is False
    purchased = await subscription_repository.session.scalar(
        select(EventOutboxEntry).where(EventOutboxEntry.event_type == "SubscriptionPurchasedEvent")
    )
    assert purchased is not None
    assert purchased.payload["is_trial"] is True


async def test_rejects_when_the_flag_is_already_spent(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await _create_trial_plan(plan_repository)
    actor = await user_repository.create(CreateUserDto(name="trial-spent-2"))
    await user_repository.update_fields(actor.id, UpdateUserDto(is_trial_available=False))
    actor = await user_repository.find_by_id(actor.id)
    purchase_use_case = PurchaseSubscriptionUseCase(
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
    use_case = ActivateTrialSubscriptionUseCase(
        user_repository,
        plan_repository,
        PricingRepository(subscription_repository.session),
        make_eligibility(subscription_repository.session),
        purchase_use_case,
        uow,
    )

    with pytest.raises(ValidationError):
        await use_case(actor)


async def test_a_second_activation_with_a_stale_actor_is_rejected(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    # A double tap: both updates loaded the user before either spent the
    # flag, so both carry is_trial_available=True.
    await _create_trial_plan(plan_repository)
    actor = await user_repository.create(CreateUserDto(name="trial-double-tap"))
    purchase_use_case = PurchaseSubscriptionUseCase(
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
    use_case = ActivateTrialSubscriptionUseCase(
        user_repository,
        plan_repository,
        PricingRepository(subscription_repository.session),
        make_eligibility(subscription_repository.session),
        purchase_use_case,
        uow,
    )
    first = await use_case(actor)

    with pytest.raises(ValidationError):
        await use_case(actor)

    active = await subscription_repository.get_active_by_user(actor.id)
    assert [sub.id for sub in active] == [first.id]


async def test_a_failed_activation_gives_the_trial_back(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create_trial_plan(plan_repository)
    actor = await user_repository.create(CreateUserDto(name="trial-panel-down"))
    purchase_use_case = PurchaseSubscriptionUseCase(
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

    async def _panel_down(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("panel down")

    monkeypatch.setattr(remnawave_sdk.users, "create_user", _panel_down)
    use_case = ActivateTrialSubscriptionUseCase(
        user_repository,
        plan_repository,
        PricingRepository(subscription_repository.session),
        make_eligibility(subscription_repository.session),
        purchase_use_case,
        uow,
    )

    with pytest.raises(RuntimeError):
        await use_case(actor)

    reloaded = await user_repository.find_by_id(actor.id)
    assert reloaded is not None and reloaded.is_trial_available is True


async def test_a_paid_trial_is_not_activated_for_free(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await _create_trial_plan(plan_repository, price="0.99")
    actor = await user_repository.create(CreateUserDto(name="paid-trial"))
    purchase_use_case = PurchaseSubscriptionUseCase(
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
    use_case = ActivateTrialSubscriptionUseCase(
        user_repository,
        plan_repository,
        PricingRepository(subscription_repository.session),
        make_eligibility(subscription_repository.session),
        purchase_use_case,
        uow,
    )

    with pytest.raises(ValidationError) as error:
        await use_case(actor)

    assert error.value.code is ErrorCode.TRIAL_NOT_AVAILABLE
    reloaded = await user_repository.find_by_id(actor.id)
    assert reloaded is not None and reloaded.is_trial_available is True
