from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import PaymentOrder
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PurchaseType,
    SubscriptionStatus,
)
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.gateways.repository import GatewaysRepository
from app.modules.payments import PaymentGatewayFactory, PaymentIntent
from app.modules.payments.dto import CreateCheckoutDto, PaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.payments.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.referrals import ReferralRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions import (
    CreateSubscriptionDto,
    SubscriptionRepository,
    purchase_subscription_task,
)
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from tests.modules.subscriptions.factories import make_plan_snapshot


class _FakeGateway:
    def __init__(self, *, confirmation_url: str = "https://yookassa.ru/pay/fake") -> None:
        self.confirmation_url = confirmation_url
        self.create_payment_calls: list[PaymentOrderDto] = []

    async def create_payment(self, order: PaymentOrderDto) -> PaymentIntent:
        self.create_payment_calls.append(order)
        return PaymentIntent(
            confirmation_url=self.confirmation_url, provider_payment_id="yk-fake-id"
        )


class _FakeFactory(PaymentGatewayFactory):
    def __init__(self, gateway: _FakeGateway) -> None:
        self._gateway = gateway

    def build(self, gateway_type, settings):  # type: ignore[no-untyped-def]
        return self._gateway  # type: ignore[return-value]


@pytest.fixture
def fake_gateway() -> _FakeGateway:
    return _FakeGateway()


@pytest.fixture
async def _active_yookassa(gateways_repository: GatewaysRepository, uow: UnitOfWork) -> None:
    async with uow:
        await gateways_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"shop_id": "1", "api_key": "k"}
        )
        await gateways_repository.set_active(PaymentGatewayType.YOOKASSA, True)


@pytest.fixture
def create_checkout_use_case(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    gateways_repository: GatewaysRepository,
    payment_order_repository: PaymentOrderRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    referral_repository: ReferralRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    fake_gateway: _FakeGateway,
) -> CreateCheckoutUseCase:
    return CreateCheckoutUseCase(
        plan_repository,
        user_repository,
        gateways_repository,
        payment_order_repository,
        subscription_repository,
        settings_repository,
        referral_repository,
        pricing_repository,
        uow,
        _FakeFactory(fake_gateway),
    )


@pytest.fixture
async def actor(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="checkout-buyer", telegram_id=700_001))


@pytest.fixture
async def plan(plan_repository: PlanRepository) -> PlanDto:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="checkout-test-plan",
            name="Checkout Test Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[uuid4()], external_squad=None)
    )
    return await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))


async def test_create_checkout_creates_a_pending_order_and_returns_confirmation_url(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    fake_gateway: _FakeGateway,
    actor: UserDto,
    plan: PlanDto,
) -> None:
    result = await create_checkout_use_case(
        actor,
        CreateCheckoutDto(
            user_id=actor.id,
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
        ),
    )

    assert result.confirmation_url == fake_gateway.confirmation_url
    assert len(fake_gateway.create_payment_calls) == 1


async def test_create_checkout_with_100_percent_discount_skips_the_gateway(
    create_checkout_use_case: CreateCheckoutUseCase,
    fake_gateway: _FakeGateway,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # purchase_subscription_task.kiq() is a real dispatch onto the taskiq/redis
    # broker singleton -- fine in isolation, but that singleton's connection
    # gets bound to whichever event loop first touches it, and pytest-asyncio
    # hands every test its own loop, so reusing it later in a full-suite run
    # raises "Future attached to a different loop". Faked here the same way
    # the gateway is faked above: this test only cares that the free-order
    # path dispatches the right payload, not that Redis is actually reachable.
    dispatched_calls: list[dict[str, object]] = []

    async def _fake_kiq(**kwargs: object) -> None:
        dispatched_calls.append(kwargs)

    monkeypatch.setattr(purchase_subscription_task, "kiq", _fake_kiq)

    async with uow:
        await user_repository.update_fields(actor.id, UpdateUserDto(personal_discount=100))

    result = await create_checkout_use_case(
        actor,
        CreateCheckoutDto(
            user_id=actor.id,
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
        ),
    )

    assert result.confirmation_url is None
    assert len(fake_gateway.create_payment_calls) == 0
    assert len(dispatched_calls) == 1
    assert dispatched_calls[0]["user_id"] == actor.id
    assert dispatched_calls[0]["plan_snapshot"]["plan_id"] == plan.id
    assert dispatched_calls[0]["price_paid"] == "0.00"
    assert dispatched_calls[0]["idempotency_key"]


async def test_create_checkout_rejects_purchasing_for_another_user_without_privilege(
    create_checkout_use_case: CreateCheckoutUseCase, actor: UserDto, plan: PlanDto
) -> None:
    with pytest.raises(PermissionDeniedError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id + 1,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )


async def _seed_subscription(
    subscription_repository: SubscriptionRepository,
    *,
    user_id: int,
    remnawave_user_id: int,
    plan_id: int,
) -> int:
    subscription = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user_id,
            remnawave_user_id=remnawave_user_id,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now() + timedelta(days=30),
            url=f"https://example.com/sub/{remnawave_user_id}",
            plan_snapshot=make_plan_snapshot(
                plan_id=plan_id,
                public_code="checkout-test-plan",
                name="Checkout Test Plan",
                price_paid=Decimal("500.00"),
                currency=Currency.RUB,
            ),
        )
    )
    return subscription.id


async def test_create_checkout_rejects_a_new_purchase_at_the_subscription_cap(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    subscription_repository: SubscriptionRepository,
    session: AsyncSession,
) -> None:
    # No shop_settings row is written here, so the cap is ShopSettingsDto's
    # own default (3).
    for index in range(3):
        await _seed_subscription(
            subscription_repository,
            user_id=actor.id,
            remnawave_user_id=810_000 + index,
            plan_id=plan.id,
        )

    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )

    order_count = await session.scalar(
        select(func.count()).select_from(PaymentOrder).where(PaymentOrder.user_id == actor.id)
    )
    assert order_count == 0


async def test_create_checkout_allows_a_link_availability_plan(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    fake_gateway: _FakeGateway,
    actor: UserDto,
    plan: PlanDto,
    plan_repository: PlanRepository,
) -> None:
    # LINK plans never show up in the catalog (ListActivePlansUseCase excludes
    # them), but a checkout that already knows the plan_id -- as if reached via
    # a direct link/code -- must still go through.
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=plan.id,
            availability=PlanAvailability.LINK,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )

    result = await create_checkout_use_case(
        actor,
        CreateCheckoutDto(
            user_id=actor.id,
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
        ),
    )

    assert result.confirmation_url == fake_gateway.confirmation_url


async def test_create_checkout_rejects_an_existing_availability_plan_for_a_fresh_user(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    plan_repository: PlanRepository,
) -> None:
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=plan.id,
            availability=PlanAvailability.EXISTING,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )

    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )


async def test_create_checkout_invited_plan_requires_a_referrer(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    fake_gateway: _FakeGateway,
    actor: UserDto,
    plan: PlanDto,
    plan_repository: PlanRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
) -> None:
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=plan.id,
            availability=PlanAvailability.INVITED,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )

    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )

    referrer = await user_repository.create(CreateUserDto(name="referrer", telegram_id=700_002))
    await referral_repository.create_referral(
        referrer_id=referrer.id, referred_id=actor.id, level=1
    )

    result = await create_checkout_use_case(
        actor,
        CreateCheckoutDto(
            user_id=actor.id,
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
        ),
    )

    assert result.confirmation_url == fake_gateway.confirmation_url


async def test_create_checkout_rejects_an_inactive_plan(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    plan_repository: PlanRepository,
) -> None:
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=False))

    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )


async def test_create_checkout_renew_rejects_a_target_belonging_to_another_user(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
) -> None:
    other = await user_repository.create(CreateUserDto(name="other-buyer", telegram_id=700_002))
    other_subscription_id = await _seed_subscription(
        subscription_repository,
        user_id=other.id,
        remnawave_user_id=820_001,
        plan_id=plan.id,
    )

    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=other_subscription_id,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )


async def test_checkout_rejects_an_unimplemented_gateway(
    create_checkout_use_case: CreateCheckoutUseCase, actor: UserDto, plan: PlanDto
) -> None:
    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.CRYPTOMUS,
            ),
        )


async def test_checkout_rejects_telegram_stars_from_the_web(
    create_checkout_use_case: CreateCheckoutUseCase, actor: UserDto, plan: PlanDto
) -> None:
    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.XTR,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.TELEGRAM_STARS,
            ),
        )


async def test_checkout_rejects_an_inactive_gateway(
    create_checkout_use_case: CreateCheckoutUseCase, actor: UserDto, plan: PlanDto
) -> None:
    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )


async def test_checkout_rejects_a_currency_the_gateway_does_not_settle(
    create_checkout_use_case: CreateCheckoutUseCase, actor: UserDto, plan: PlanDto
) -> None:
    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                user_id=actor.id,
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.USD,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )
