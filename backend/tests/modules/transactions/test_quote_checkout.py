from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
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
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.settings import GetAccessSettingsUseCase
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.transactions.checkout_pricing import CheckoutPricer
from app.modules.transactions.dto import QuoteCheckoutDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import CreateCheckoutUseCase, QuoteCheckoutUseCase
from app.modules.transactions.waitlist_repository import WaitlistRepository
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.subscriptions.factories import make_eligibility
from tests.modules.transactions.test_usecases import (
    _checkout_dto,
    _FakeFactory,
    _FakeGateway,
    _promocode,
)


@pytest.fixture
def pricer(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    pricing_repository: PricingRepository,
    promocode_repository: PromocodeRepository,
    uow: UnitOfWork,
) -> CheckoutPricer:
    return CheckoutPricer(
        plan_repository,
        user_repository,
        make_eligibility(plan_repository.session),
        pricing_repository,
        uow,
        promocode_repository,
    )


@pytest.fixture
def quote_use_case(pricer: CheckoutPricer, uow: UnitOfWork) -> QuoteCheckoutUseCase:
    return QuoteCheckoutUseCase(pricer, uow)


@pytest.fixture
def checkout_use_case(
    pricer: CheckoutPricer,
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    gateway_repository: GatewayRepository,
    transaction_repository: TransactionRepository,
    subscription_repository: SubscriptionRepository,
    settings_repository: SettingsRepository,
    waitlist_repository: WaitlistRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> CreateCheckoutUseCase:
    return CreateCheckoutUseCase(
        pricer,
        user_repository,
        gateway_repository,
        transaction_repository,
        subscription_repository,
        make_eligibility(plan_repository.session),
        uow,
        _FakeFactory(_FakeGateway()),
        RecordingDispatch(),
        GetAccessSettingsUseCase(settings_repository, uow),
        waitlist_repository,
        settings_repository,
        config,
        event_publisher,
    )


@pytest.fixture
async def actor(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="quote-buyer", telegram_id=700_101))


@pytest.fixture
async def plan(plan_repository: PlanRepository) -> PlanDto:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="quote-test-plan",
            name="Quote Test Plan",
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


@pytest.fixture
async def _active_yookassa(gateway_repository: GatewayRepository, uow: UnitOfWork) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"shop_id": "1", "api_key": "k"}
        )
        await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, True)


def _quote_dto(plan: PlanDto) -> QuoteCheckoutDto:
    return QuoteCheckoutDto(plan_id=plan.id, duration_days=30, currency=Currency.RUB)


async def _set(
    user_repository: UserRepository, uow: UnitOfWork, actor: UserDto, fields: UpdateUserDto
) -> UserDto:
    async with uow:
        await user_repository.update_fields(actor.id, fields)
    user = await user_repository.find_by_id(actor.id)
    assert user is not None
    return user


async def test_quote_matches_the_checkout_price(
    quote_use_case: QuoteCheckoutUseCase,
    checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    buyer = await _set(user_repository, uow, actor, UpdateUserDto(personal_discount=10))

    quote = await quote_use_case(buyer, _quote_dto(plan))
    result = await checkout_use_case(buyer, _checkout_dto(buyer, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert quote.final_price == order.final_price
    assert quote.discount_source is DiscountSource.PERSONAL


async def test_quote_ignores_a_discount_from_an_ended_promocode(
    quote_use_case: QuoteCheckoutUseCase,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    promocode_repository: PromocodeRepository,
    uow: UnitOfWork,
) -> None:
    dead = await _promocode(promocode_repository, "QUOTEDEAD", live=False)
    buyer = await _set(
        user_repository,
        uow,
        actor,
        UpdateUserDto(purchase_discount=20, purchase_discount_promocode_id=dead),
    )

    quote = await quote_use_case(buyer, _quote_dto(plan))

    assert quote.discount_percent == 0


async def test_quote_refuses_a_hidden_plan_like_a_missing_one(
    quote_use_case: QuoteCheckoutUseCase,
    actor: UserDto,
    plan: PlanDto,
    plan_repository: PlanRepository,
) -> None:
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=plan.id,
            availability=PlanAvailability.LINK,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )

    with pytest.raises(NotFoundError) as error:
        await quote_use_case(actor, _quote_dto(plan))

    assert error.value.code is ErrorCode.PLAN_NOT_FOUND


async def test_quote_does_not_spend_the_purchase_discount(
    quote_use_case: QuoteCheckoutUseCase,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    buyer = await _set(user_repository, uow, actor, UpdateUserDto(purchase_discount=20))

    quote = await quote_use_case(buyer, _quote_dto(plan))

    assert quote.discount_source is DiscountSource.PURCHASE
    user = await user_repository.find_by_id(actor.id)
    assert user is not None and user.purchase_discount == 20
