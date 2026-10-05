from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PaymentGatewayType, PlanType, PurchaseType, Role, RoundingMode
from app.core.ports import EventPublisher
from app.modules.gateways.repository import GatewayRepository
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SwitchAnchorCurrencyDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.plans.usecases import SwitchAnchorCurrencyUseCase
from app.modules.pricing.dto import UpdateCurrencyRateDto
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.usecases import UpdateCurrencyRateUseCase
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals.repository import ReferralRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import ListActivePlansUseCase
from app.modules.transactions import PaymentGatewayFactory, PaymentIntent
from app.modules.transactions.dto import CreateCheckoutDto, TransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases.create_checkout import CreateCheckoutUseCase
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.subscriptions.factories import make_eligibility

OWNER = UserDto(name="owner", role=Role.OWNER)


class _FakeGateway:
    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        return PaymentIntent(
            confirmation_url="https://yookassa.ru/pay/fake", provider_payment_id="yk-fake-id"
        )


class _FakeFactory(PaymentGatewayFactory):
    def __init__(self) -> None:
        self._gateway = _FakeGateway()

    def build(self, gateway_type, settings):  # type: ignore[no-untyped-def]
        return self._gateway  # type: ignore[return-value]


@pytest.fixture
def transaction_repository(session: AsyncSession) -> TransactionRepository:
    return TransactionRepository(session)


async def _create_active_plan(plan_repository: PlanRepository, public_code: str) -> PlanDto:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code=public_code,
            name="Integration Plan",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("2.00"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[uuid4()], external_squad=None)
    )
    return await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))


async def _rub_catalog_price(
    plan: PlanDto,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> Decimal:
    list_active_plans = ListActivePlansUseCase(
        plan_repository,
        PricingRepository(plan_repository.session),
        make_eligibility(plan_repository.session),
        uow,
    )
    plans = await list_active_plans(OWNER)
    catalog_plan = next(p for p in plans if p.id == plan.id)
    item = catalog_plan.durations[0]
    return next(price for price in item.prices if price.currency is Currency.RUB).price


async def test_rate_change_moves_catalog_but_not_existing_order(
    plan_repository: PlanRepository,
    pricing_repository: PricingRepository,
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    gateway_repository: GatewayRepository,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"shop_id": "1", "api_key": "k"}
        )
        await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, True)

    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("90"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )

    user = await user_repository.create(
        CreateUserDto(name="integration-buyer", telegram_id=800_001)
    )
    plan = await _create_active_plan(plan_repository, "integration-order-plan")

    create_checkout = CreateCheckoutUseCase(
        plan_repository,
        user_repository,
        gateway_repository,
        transaction_repository,
        subscription_repository,
        make_eligibility(plan_repository.session),
        pricing_repository,
        uow,
        _FakeFactory(),
        RecordingDispatch(),
        PromocodeRepository(plan_repository.session),
    )
    result = await create_checkout(
        user,
        CreateCheckoutDto(
            user_id=user.id,
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
        ),
    )

    order = await transaction_repository.get_by_id(result.order_id)
    assert order.base_price == Decimal("180")  # 2.00 * 90

    await UpdateCurrencyRateUseCase(pricing_repository, uow, event_publisher)(
        OWNER,
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("100"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        ),
    )

    catalog_price = await _rub_catalog_price(
        plan, plan_repository, subscription_repository, referral_repository, pricing_repository, uow
    )
    assert catalog_price == Decimal("200")  # 2.00 * 100

    reloaded_order = await transaction_repository.get_by_id(result.order_id)
    assert reloaded_order.base_price == Decimal("180")


async def test_switch_anchor_leaves_catalog_stable(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    await pricing_repository.get_rate_table()
    await pricing_repository.update_rate(
        UpdateCurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("95"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        )
    )
    plan = await _create_active_plan(plan_repository, "integration-anchor-plan")

    before = await _rub_catalog_price(
        plan, plan_repository, subscription_repository, referral_repository, pricing_repository, uow
    )

    await SwitchAnchorCurrencyUseCase(
        pricing_repository,
        plan_repository,
        addon_repository,
        TransactionRepository(plan_repository.session),
        uow,
        event_publisher,
    )(OWNER, SwitchAnchorCurrencyDto(new_anchor=Currency.RUB))

    after = await _rub_catalog_price(
        plan, plan_repository, subscription_repository, referral_repository, pricing_repository, uow
    )

    assert abs(after - before) <= Decimal("1")
