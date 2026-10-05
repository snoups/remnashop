from datetime import timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PromocodeRewardType,
    PurchaseType,
    Role,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.gateways.repository import GatewayRepository
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
from app.modules.promocodes.dto import CreatePromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals import ReferralRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions import (
    CreateSubscriptionDto,
    SubscriptionRepository,
)
from app.modules.transactions import PaymentGatewayFactory, PaymentIntent
from app.modules.transactions.dto import CreateCheckoutDto, TransactionDto
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.transactions.usecases.create_test_payment import CreateTestPaymentUseCase
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.subscriptions.factories import make_eligibility, make_plan_snapshot


class _FakeGateway:
    def __init__(self, *, confirmation_url: str = "https://yookassa.ru/pay/fake") -> None:
        self.confirmation_url = confirmation_url
        self.create_payment_calls: list[TransactionDto] = []

    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
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
async def _active_yookassa(gateway_repository: GatewayRepository, uow: UnitOfWork) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"shop_id": "1", "api_key": "k"}
        )
        await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, True)


@pytest.fixture
def purchase_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def create_checkout_use_case(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    gateway_repository: GatewayRepository,
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    referral_repository: ReferralRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    fake_gateway: _FakeGateway,
    purchase_dispatch: RecordingDispatch,
    promocode_repository: PromocodeRepository,
) -> CreateCheckoutUseCase:
    return CreateCheckoutUseCase(
        plan_repository,
        user_repository,
        gateway_repository,
        transaction_repository,
        subscription_repository,
        make_eligibility(plan_repository.session),
        pricing_repository,
        uow,
        _FakeFactory(fake_gateway),
        purchase_dispatch,
        promocode_repository,
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
    purchase_dispatch: RecordingDispatch,
) -> None:
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
    assert len(purchase_dispatch.messages) == 1
    assert purchase_dispatch.messages[0]["user_id"] == actor.id
    assert purchase_dispatch.messages[0]["plan_snapshot"]["plan_id"] == plan.id
    assert purchase_dispatch.messages[0]["price_paid"] == "0.00"
    assert purchase_dispatch.messages[0]["idempotency_key"]


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
        select(func.count()).select_from(Transaction).where(Transaction.user_id == actor.id)
    )
    assert order_count == 0


async def test_create_checkout_link_plan_requires_its_code(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    fake_gateway: _FakeGateway,
    actor: UserDto,
    plan: PlanDto,
    plan_repository: PlanRepository,
) -> None:
    # LINK plans never show up in the catalog; the link's code is the access
    # control. Without it the plan answers exactly like a missing one.
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=plan.id,
            availability=PlanAvailability.LINK,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )

    def checkout(code: Optional[str]) -> CreateCheckoutDto:
        return CreateCheckoutDto(
            user_id=actor.id,
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
            plan_code=code,
        )

    result = await create_checkout_use_case(actor, checkout(plan.public_code))
    assert result.confirmation_url == fake_gateway.confirmation_url

    for code in (None, "wrong-code"):
        with pytest.raises(NotFoundError):
            await create_checkout_use_case(actor, checkout(code))


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

    with pytest.raises(NotFoundError):
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
    uow: UnitOfWork,
) -> None:
    # Committed, not just flushed: the refused checkout below rolls its own
    # transaction back, which would otherwise take this setup with it.
    async with uow:
        await plan_repository.update_access(
            UpdatePlanAccessDto(
                plan_id=plan.id,
                availability=PlanAvailability.INVITED,
                allowed_telegram_ids=[],
                allowed_emails=[],
            )
        )

    with pytest.raises(NotFoundError):
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

    with pytest.raises(NotFoundError):
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


async def test_checkout_asks_for_an_email_when_the_gateway_needs_a_receipt(
    create_checkout_use_case: CreateCheckoutUseCase,
    gateway_repository: GatewayRepository,
    uow: UnitOfWork,
    fake_gateway: _FakeGateway,
    actor: UserDto,
    plan: PlanDto,
) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"shop_id": "1", "api_key": "k", "vat_code": "1"}
        )
        await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, True)

    def _dto(email: Optional[str]) -> CreateCheckoutDto:
        return CreateCheckoutDto(
            user_id=actor.id,
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
            customer_email=email,
        )

    with pytest.raises(ValidationError):
        await create_checkout_use_case(actor, _dto(None))

    await create_checkout_use_case(actor, _dto("buyer@example.com"))
    assert fake_gateway.create_payment_calls[0].customer_email == "buyer@example.com"


async def test_checkout_rejects_an_unimplemented_gateway(
    create_checkout_use_case: CreateCheckoutUseCase,
    actor: UserDto,
    plan: PlanDto,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # every PaymentGatewayType has an adapter, so one is removed to get a
    # miss; the checkout guard reads the real registry, not the fake factory
    monkeypatch.delitem(GATEWAY_REGISTRY, PaymentGatewayType.YOOKASSA)
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


async def test_test_payment_persists_a_pending_test_order_hidden_from_the_order_list(
    gateway_repository: GatewayRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    fake_gateway: _FakeGateway,
    _active_yookassa: None,
) -> None:
    owner = await user_repository.create(CreateUserDto(name="owner", role=Role.OWNER))
    use_case = CreateTestPaymentUseCase(
        gateway_repository,
        transaction_repository,
        pricing_repository,
        uow,
        _FakeFactory(fake_gateway),
    )

    result = await use_case(owner, PaymentGatewayType.YOOKASSA)

    assert result.confirmation_url == fake_gateway.confirmation_url
    order = await transaction_repository.get_by_id(result.order_id)
    assert order.is_test
    assert order.status is TransactionStatus.PENDING
    assert order.external_payment_id == "yk-fake-id"
    assert order.currency is Currency.RUB
    assert await transaction_repository.list_paginated() == ([], 0)


async def test_test_payment_rejects_an_unconfigured_gateway(
    gateway_repository: GatewayRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    fake_gateway: _FakeGateway,
) -> None:
    owner = await user_repository.create(CreateUserDto(name="owner", role=Role.OWNER))
    use_case = CreateTestPaymentUseCase(
        gateway_repository,
        transaction_repository,
        pricing_repository,
        uow,
        _FakeFactory(fake_gateway),
    )

    with pytest.raises(ValidationError):
        await use_case(owner, PaymentGatewayType.YOOKASSA)
    assert fake_gateway.create_payment_calls == []


def _checkout_dto(actor: UserDto, plan: PlanDto) -> CreateCheckoutDto:
    return CreateCheckoutDto(
        user_id=actor.id,
        plan_id=plan.id,
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        gateway_type=PaymentGatewayType.YOOKASSA,
    )


async def test_checkout_spends_the_purchase_discount_with_the_order(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.update_fields(actor.id, UpdateUserDto(purchase_discount=20))

    result = await create_checkout_use_case(actor, _checkout_dto(actor, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert order.discount_source is DiscountSource.PURCHASE
    assert order.discount_percent == 20
    user = await user_repository.get_by_id(actor.id)
    assert user is not None and user.purchase_discount == 0


async def test_spend_purchase_discount_is_a_one_shot_claim(
    actor: UserDto, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    # two checkouts quoted against the same discount: only one may spend it
    async with uow:
        await user_repository.update_fields(actor.id, UpdateUserDto(purchase_discount=20))
        first = await user_repository.spend_purchase_discount(actor.id, 20)
        second = await user_repository.spend_purchase_discount(actor.id, 20)

    assert (first, second) == (True, False)


async def test_a_personal_discount_order_leaves_the_purchase_discount_alone(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.update_fields(
            actor.id, UpdateUserDto(personal_discount=30, purchase_discount=10)
        )
    actor = await user_repository.get_by_id(actor.id)  # type: ignore[assignment]

    await create_checkout_use_case(actor, _checkout_dto(actor, plan))

    assert (await user_repository.get_by_id(actor.id)).purchase_discount == 10  # type: ignore[union-attr]


async def _promocode(promocode_repository: PromocodeRepository, code: str, *, live: bool) -> int:
    promo = await promocode_repository.create(
        CreatePromocodeDto(code=code, reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=20)
    )
    if not live:
        await promocode_repository.update(
            UpdatePromocodeDto(promocode_id=promo.id, is_active=False)
        )
    return promo.id


async def test_a_discount_from_a_dead_promocode_is_dropped(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    promocode_repository: PromocodeRepository,
    uow: UnitOfWork,
) -> None:
    dead = await _promocode(promocode_repository, "DEADDISC", live=False)
    async with uow:
        await user_repository.update_fields(
            actor.id, UpdateUserDto(purchase_discount=20, purchase_discount_promocode_id=dead)
        )
    buyer = await user_repository.get_by_id(actor.id)
    assert buyer is not None

    result = await create_checkout_use_case(buyer, _checkout_dto(buyer, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert order.discount_percent == 0
    user = await user_repository.get_by_id(actor.id)
    assert user is not None
    assert (user.purchase_discount, user.purchase_discount_promocode_id) == (0, None)


async def test_the_live_smaller_discount_applies_when_the_larger_ones_promocode_is_dead(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    promocode_repository: PromocodeRepository,
    uow: UnitOfWork,
) -> None:
    dead = await _promocode(promocode_repository, "DEADBIG", live=False)
    live = await _promocode(promocode_repository, "LIVESMALL", live=True)
    async with uow:
        await user_repository.update_fields(
            actor.id,
            UpdateUserDto(
                personal_discount=30,
                personal_discount_promocode_id=dead,
                purchase_discount=10,
                purchase_discount_promocode_id=live,
            ),
        )
    buyer = await user_repository.get_by_id(actor.id)
    assert buyer is not None

    result = await create_checkout_use_case(buyer, _checkout_dto(buyer, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert order.discount_percent == 10


async def test_an_admin_granted_discount_survives(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.update_fields(actor.id, UpdateUserDto(personal_discount=15))
    buyer = await user_repository.get_by_id(actor.id)
    assert buyer is not None

    result = await create_checkout_use_case(buyer, _checkout_dto(buyer, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert order.discount_percent == 15
