import asyncio
import contextlib
import dataclasses
from datetime import timedelta
from decimal import Decimal
from typing import Final, Optional
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core.db.models import (
    CurrencyRate,
    EventOutboxEntry,
    Plan,
    PricingSettings,
    ShopSettings,
    Subscription,
    Transaction,
    User,
)
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
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    NotFoundError,
    PaymentGatewayError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.gateways.repository import GatewayRepository
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanAccessDto,
    UpdatePlanDiscountDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.promocodes.dto import CreatePromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals import ReferralRepository
from app.modules.settings import GetAccessSettingsUseCase
from app.modules.settings.dto import (
    UpdateAccessSettingsDto,
    UpdateBotSettingsDto,
    UpdateShopSettingsDto,
)
from app.modules.settings.repository import SettingsRepository
from app.modules.subscriptions import (
    CreateSubscriptionDto,
    SubscriptionRepository,
)
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.usecases.purchase_subscription import STALE_CLAIM_AFTER
from app.modules.transactions import PaymentGatewayFactory, PaymentIntent
from app.modules.transactions.dto import CreateCheckoutDto, TransactionDto
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import CreateCheckoutUseCase, CreateTestPaymentUseCase
from app.modules.transactions.waitlist_repository import WaitlistRepository
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UpdateUserDto, UserDto
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.events import RecordingEventPublisher
from tests.modules.settings.factories import SHOP_SETTINGS_FIELDS
from tests.modules.subscriptions.factories import make_eligibility, make_plan_snapshot

_SHOP_FIELDS: Final[set[str]] = {field.name for field in dataclasses.fields(UpdateShopSettingsDto)}


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
        self.settings = settings
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
    waitlist_repository: WaitlistRepository,
    event_publisher: EventPublisher,
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
        GetAccessSettingsUseCase(settings_repository, uow),
        waitlist_repository,
        settings_repository,
        event_publisher,
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
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
        ),
    )

    assert result.confirmation_url == fake_gateway.confirmation_url
    assert len(fake_gateway.create_payment_calls) == 1


async def test_create_checkout_publishes_the_new_order(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    session: AsyncSession,
) -> None:
    result = await create_checkout_use_case(
        actor,
        CreateCheckoutDto(
            plan_id=plan.id,
            duration_days=30,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
        ),
    )

    row = await session.scalar(
        select(EventOutboxEntry).where(EventOutboxEntry.event_type == "CheckoutCreatedEvent")
    )
    assert row is not None
    assert row.payload["order_id"] == result.order_id
    assert row.payload["user"]["id"] == actor.id
    assert row.payload["gateway_type"] == "YOOKASSA"


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


async def test_concurrent_free_checkouts_stop_at_the_cap(engine: AsyncEngine) -> None:
    # Separate connections, since an advisory xact lock in one shared session
    # serializes nothing; the seed rows are committed and cleaned up by hand.
    attempts = 3

    async def one_checkout(conn: AsyncConnection, buyer: UserDto, plan_id: int) -> str:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        uow = UnitOfWork(session)
        use_case = CreateCheckoutUseCase(
            PlanRepository(session),
            UserRepository(session),
            GatewayRepository(session),
            TransactionRepository(session),
            SubscriptionRepository(session),
            make_eligibility(session),
            PricingRepository(session),
            uow,
            _FakeFactory(_FakeGateway()),
            RecordingDispatch(),
            PromocodeRepository(session),
            GetAccessSettingsUseCase(SettingsRepository(session), uow),
            WaitlistRepository(session),
            SettingsRepository(session),
            RecordingEventPublisher(),
        )
        try:
            await use_case(
                buyer,
                CreateCheckoutDto(
                    plan_id=plan_id,
                    duration_days=30,
                    currency=Currency.RUB,
                    purchase_type=PurchaseType.NEW,
                    gateway_type=PaymentGatewayType.YOOKASSA,
                ),
            )
            return "ok"
        except ValidationError as error:
            assert error.code is ErrorCode.SUBSCRIPTION_LIMIT_REACHED
            return "rejected"
        finally:
            await session.close()

    # the checkouts commit seed rows into these singletons; a table empty
    # before the test is emptied again afterwards
    singletons = (ShopSettings, CurrencyRate, PricingSettings)
    async with engine.connect() as conn:
        shop_before = await SettingsRepository(
            AsyncSession(bind=conn, expire_on_commit=False)
        ).get_shop_settings()
        empty_before = [
            model
            for model in singletons
            if not await conn.scalar(select(func.count()).select_from(model))
        ]

    try:
        async with contextlib.AsyncExitStack() as stack:
            conns = [await stack.enter_async_context(engine.connect()) for _ in range(attempts + 1)]

            setup = AsyncSession(bind=conns[0], expire_on_commit=False)
            await SettingsRepository(setup).update_shop_settings(
                UpdateShopSettingsDto(
                    **{
                        **shop_before.model_dump(include=_SHOP_FIELDS),
                        "max_active_subscriptions": 1,
                    },
                    fields_set=SHOP_SETTINGS_FIELDS,
                )
            )
            buyer = await UserRepository(setup).create(
                CreateUserDto(name="checkout-cap-buyer", telegram_id=90_211)
            )
            plans = PlanRepository(setup)
            plan = await plans.create(
                CreatePlanDto(
                    public_code="checkout-cap-race",
                    name="checkout-cap-race",
                    type=PlanType.BOTH,
                    traffic_limit=100,
                    device_limit=3,
                )
            )
            await plans.set_durations(
                SetPlanDurationsDto(
                    plan_id=plan.id,
                    durations=[
                        SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("500.00"))
                    ],
                )
            )
            await plans.update_squads(
                UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
            )
            await plans.update_discount(
                UpdatePlanDiscountDto(
                    plan_id=plan.id,
                    discount_percent=100,
                    discount_starts_at=None,
                    discount_ends_at=None,
                )
            )
            await plans.update(UpdatePlanDto(plan_id=plan.id, is_active=True))
            await setup.commit()
            await setup.close()

            results = await asyncio.gather(
                *(one_checkout(conns[i + 1], buyer, plan.id) for i in range(attempts))
            )
            assert results.count("ok") == 1
            assert results.count("rejected") == attempts - 1

            check = AsyncSession(bind=conns[0], expire_on_commit=False)
            orders = await check.scalar(
                select(func.count()).select_from(Transaction).where(Transaction.user_id == buyer.id)
            )
            assert orders == 1
            await check.close()
    finally:
        async with engine.begin() as cleanup:
            buyers = select(User.id).where(User.telegram_id == 90_211)
            await cleanup.execute(delete(Transaction).where(Transaction.user_id.in_(buyers)))
            await cleanup.execute(delete(Plan).where(Plan.public_code == "checkout-cap-race"))
            await cleanup.execute(delete(User).where(User.telegram_id == 90_211))
            for model in empty_before:
                await cleanup.execute(delete(model))
            if ShopSettings not in empty_before:
                await SettingsRepository(AsyncSession(bind=cleanup)).update_shop_settings(
                    UpdateShopSettingsDto(
                        **shop_before.model_dump(include=_SHOP_FIELDS),
                        fields_set=SHOP_SETTINGS_FIELDS,
                    )
                )


async def test_a_provisioned_order_awaiting_its_link_is_not_counted_twice(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    subscription_repository: SubscriptionRepository,
    idempotency_repository: PurchaseIdempotencyRepository,
    purchase_dispatch: RecordingDispatch,
    fake_gateway: _FakeGateway,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await settings_repository.update_shop_settings(
            UpdateShopSettingsDto(
                max_active_subscriptions=2,
                device_single_reset_enabled=True,
                device_single_reset_cooldown_hours=0,
                device_all_reset_enabled=True,
                device_all_reset_cooldown_hours=0,
                link_reset_enabled=True,
                link_reset_cooldown_hours=0,
                fields_set=SHOP_SETTINGS_FIELDS,
            )
        )
        await user_repository.update_fields(actor.id, UpdateUserDto(personal_discount=100))
    checkout = CreateCheckoutDto(
        plan_id=plan.id,
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        gateway_type=PaymentGatewayType.YOOKASSA,
    )
    await create_checkout_use_case(actor, checkout)

    # the order's fulfilment ran; the reconcile sweep hasn't linked it yet
    key = purchase_dispatch.messages[0]["idempotency_key"]
    async with uow:
        subscription_id = await _seed_subscription(
            subscription_repository, user_id=actor.id, remnawave_user_id=820_000, plan_id=plan.id
        )
        token = await idempotency_repository.claim(key, stale_after=STALE_CLAIM_AFTER)
        await idempotency_repository.link(key, subscription_id, token)
        await user_repository.update_fields(actor.id, UpdateUserDto(personal_discount=0))

    result = await create_checkout_use_case(actor, checkout)

    assert result.confirmation_url == fake_gateway.confirmation_url


async def test_an_open_order_counts_as_history_for_a_new_only_plan(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    plan_repository: PlanRepository,
) -> None:
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=plan.id,
            availability=PlanAvailability.NEW,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )
    checkout = CreateCheckoutDto(
        plan_id=plan.id,
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        gateway_type=PaymentGatewayType.YOOKASSA,
    )

    await create_checkout_use_case(actor, checkout)

    with pytest.raises(NotFoundError) as error:
        await create_checkout_use_case(actor, checkout)
    assert error.value.code is ErrorCode.PLAN_NOT_FOUND


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
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )


async def test_checkout_hands_stars_the_bot_token(
    create_checkout_use_case: CreateCheckoutUseCase,
    gateway_repository: GatewayRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    actor: UserDto,
    plan: PlanDto,
    fake_gateway: _FakeGateway,
) -> None:
    async with uow:
        await settings_repository.update_bot_settings(
            UpdateBotSettingsDto(token="123:abc", secret_token="hook-secret")
        )
        await gateway_repository.set_active(PaymentGatewayType.TELEGRAM_STARS, True)

    await create_checkout_use_case(actor, _stars_checkout(plan))

    factory = create_checkout_use_case._gateway_factory
    assert len(fake_gateway.create_payment_calls) == 1
    assert factory.settings["bot_token"] == "123:abc"  # type: ignore[attr-defined]


def _stars_checkout(plan: PlanDto) -> CreateCheckoutDto:
    return CreateCheckoutDto(
        plan_id=plan.id,
        duration_days=30,
        currency=Currency.XTR,
        purchase_type=PurchaseType.NEW,
        gateway_type=PaymentGatewayType.TELEGRAM_STARS,
    )


async def test_checkout_refuses_stars_while_the_bot_has_no_webhook_secret(
    create_checkout_use_case: CreateCheckoutUseCase,
    gateway_repository: GatewayRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    actor: UserDto,
    plan: PlanDto,
    fake_gateway: _FakeGateway,
) -> None:
    async with uow:
        await settings_repository.update_bot_settings(UpdateBotSettingsDto(token="123:abc"))
        await gateway_repository.set_active(PaymentGatewayType.TELEGRAM_STARS, True)

    with pytest.raises(ValidationError) as error:
        await create_checkout_use_case(actor, _stars_checkout(plan))

    assert error.value.code is ErrorCode.GATEWAY_NOT_AVAILABLE
    assert fake_gateway.create_payment_calls == []


async def test_checkout_refuses_stars_before_a_paid_purchase_when_required(
    create_checkout_use_case: CreateCheckoutUseCase,
    gateway_repository: GatewayRepository,
    settings_repository: SettingsRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    actor: UserDto,
    plan: PlanDto,
) -> None:
    async with uow:
        await settings_repository.update_bot_settings(
            UpdateBotSettingsDto(token="123:abc", secret_token="hook-secret")
        )
        await gateway_repository.update_settings(
            PaymentGatewayType.TELEGRAM_STARS, {"require_paid_purchase": "true"}
        )
        await gateway_repository.set_active(PaymentGatewayType.TELEGRAM_STARS, True)

    with pytest.raises(ValidationError) as error:
        await create_checkout_use_case(actor, _stars_checkout(plan))

    assert error.value.code is ErrorCode.GATEWAY_NOT_AVAILABLE
    count = await transaction_repository.session.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.user_id == actor.id)
    )
    assert count == 0


async def test_checkout_rejects_an_inactive_gateway(
    create_checkout_use_case: CreateCheckoutUseCase, actor: UserDto, plan: PlanDto
) -> None:
    with pytest.raises(ValidationError):
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
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
        RecordingEventPublisher(),
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
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await use_case(owner, PaymentGatewayType.YOOKASSA)
    assert fake_gateway.create_payment_calls == []


def _checkout_dto(actor: UserDto, plan: PlanDto) -> CreateCheckoutDto:
    return CreateCheckoutDto(
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
    user = await user_repository.find_by_id(actor.id)
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
    actor = await user_repository.find_by_id(actor.id)  # type: ignore[assignment]

    await create_checkout_use_case(actor, _checkout_dto(actor, plan))

    assert (await user_repository.find_by_id(actor.id)).purchase_discount == 10  # type: ignore[union-attr]


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
    buyer = await user_repository.find_by_id(actor.id)
    assert buyer is not None

    result = await create_checkout_use_case(buyer, _checkout_dto(buyer, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert order.discount_percent == 0
    user = await user_repository.find_by_id(actor.id)
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
    buyer = await user_repository.find_by_id(actor.id)
    assert buyer is not None

    result = await create_checkout_use_case(buyer, _checkout_dto(buyer, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert order.discount_percent == 10


async def test_a_personal_promocode_discount_is_not_flagged_as_a_purchase_promocode(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    promocode_repository: PromocodeRepository,
    uow: UnitOfWork,
) -> None:
    live = await _promocode(promocode_repository, "LIVEPERSONAL", live=True)
    async with uow:
        await user_repository.update_fields(
            actor.id, UpdateUserDto(personal_discount=15, personal_discount_promocode_id=live)
        )
    buyer = await user_repository.find_by_id(actor.id)
    assert buyer is not None

    result = await create_checkout_use_case(buyer, _checkout_dto(buyer, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert (order.discount_source, order.discount_promocode_id) == (DiscountSource.PERSONAL, live)
    assert order.discount_from_promocode is False


class _FailingGateway(_FakeGateway):
    async def create_payment(self, order: TransactionDto) -> PaymentIntent:
        raise RuntimeError("provider down")


async def test_a_gateway_failure_fails_the_order_and_hands_the_discount_back(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    fake_gateway: _FakeGateway,
    actor: UserDto,
    plan: PlanDto,
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await user_repository.update_fields(actor.id, UpdateUserDto(purchase_discount=20))
    create_checkout_use_case._gateway_factory = _FakeFactory(_FailingGateway())  # type: ignore[assignment]

    with pytest.raises(PaymentGatewayError, match="RuntimeError"):
        await create_checkout_use_case(actor, _checkout_dto(actor, plan))

    orders, _ = await transaction_repository.list_paginated(user_id=actor.id)
    assert [order.status for order in orders] == [TransactionStatus.FAILED]
    restored = await user_repository.find_by_id(actor.id)
    assert restored is not None
    assert (restored.purchase_discount, restored.purchase_discount_promocode_id) == (20, None)


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
    buyer = await user_repository.find_by_id(actor.id)
    assert buyer is not None

    result = await create_checkout_use_case(buyer, _checkout_dto(buyer, plan))

    order = await transaction_repository.get_by_id(result.order_id)
    assert order.discount_percent == 15


async def test_create_checkout_renew_refuses_a_disabled_subscription(
    create_checkout_use_case: CreateCheckoutUseCase,
    _active_yookassa: None,
    actor: UserDto,
    plan: PlanDto,
    subscription_repository: SubscriptionRepository,
) -> None:
    subscription_id = await _seed_subscription(
        subscription_repository, user_id=actor.id, remnawave_user_id=820_101, plan_id=plan.id
    )
    await subscription_repository.session.execute(
        update(Subscription)
        .where(Subscription.id == subscription_id)
        .values(status=SubscriptionStatus.DISABLED)
    )

    with pytest.raises(ValidationError) as error:
        await create_checkout_use_case(
            actor,
            CreateCheckoutDto(
                plan_id=plan.id,
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=subscription_id,
                gateway_type=PaymentGatewayType.YOOKASSA,
            ),
        )

    assert error.value.code is ErrorCode.SUBSCRIPTION_DISABLED


async def test_checkout_with_payments_off_refuses_and_waitlists_the_buyer(
    create_checkout_use_case: CreateCheckoutUseCase,
    settings_repository: SettingsRepository,
    waitlist_repository: WaitlistRepository,
    uow: UnitOfWork,
    actor: UserDto,
    plan: PlanDto,
) -> None:
    async with uow:
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(payments_enabled=False)
        )

    for _ in range(2):
        with pytest.raises(PermissionDeniedError) as error:
            await create_checkout_use_case(
                actor,
                CreateCheckoutDto(
                    plan_id=plan.id,
                    duration_days=30,
                    currency=Currency.RUB,
                    purchase_type=PurchaseType.NEW,
                    gateway_type=PaymentGatewayType.YOOKASSA,
                ),
            )
        assert error.value.code is ErrorCode.PAYMENTS_DISABLED

    async with uow:
        assert await waitlist_repository.claim_batch(100, set()) == [actor.id]


async def test_payments_gate_fires_before_pricing_for_a_full_discount_order(
    create_checkout_use_case: CreateCheckoutUseCase,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    actor: UserDto,
    plan: PlanDto,
    purchase_dispatch: RecordingDispatch,
) -> None:
    # the gate runs before the quote, so a free order never gets past it
    async with uow:
        await user_repository.update_fields(actor.id, UpdateUserDto(personal_discount=100))
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(payments_enabled=False)
        )

    with pytest.raises(PermissionDeniedError) as error:
        await create_checkout_use_case(actor, _checkout_dto(actor, plan))

    assert error.value.code is ErrorCode.PAYMENTS_DISABLED
    assert await session.scalar(select(func.count()).select_from(Transaction)) == 0
    assert purchase_dispatch.messages == []
