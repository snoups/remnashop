from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.ad_link_attribution import AdLinkAttribution
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AdLinkChannel,
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
    Role,
    RoundingMode,
)
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.advertising.dto import (
    CreateAdLinkDto,
    GetAdLinkStatsDto,
    GetAdvertisingSummaryDto,
    ListAdLinkAttributedUsersDto,
    ListAdLinksDto,
    UpdateAdLinkDto,
)
from app.modules.advertising.repository import AdLinkRepository
from app.modules.advertising.usecases import (
    CreateAdLinkUseCase,
    DeleteAdLinkUseCase,
    GenerateAdLinkCodeUseCase,
    GetAdLinkStatsUseCase,
    GetAdvertisingSummaryUseCase,
    ListAdLinkAttributedUsersUseCase,
    ListAdLinksUseCase,
    UpdateAdLinkUseCase,
)
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.pricing.dto import UpdateCurrencyRateDto
from app.modules.pricing.repository import PricingRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def test_owner_can_create_ad_link(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    use_case = CreateAdLinkUseCase(ad_link_repository, uow)

    ad_link = await use_case(OWNER, CreateAdLinkDto(name="YouTube", code="yt-1"))

    assert ad_link.code == "yt-1"
    assert ad_link.is_active is True


async def test_regular_user_cannot_create_ad_link(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    use_case = CreateAdLinkUseCase(ad_link_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, CreateAdLinkDto(name="YouTube", code="yt-2"))


async def test_create_ad_link_duplicate_code_raises_conflict(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    use_case = CreateAdLinkUseCase(ad_link_repository, uow)
    await use_case(OWNER, CreateAdLinkDto(name="A", code="dup-uc"))

    with pytest.raises(ConflictError):
        await use_case(OWNER, CreateAdLinkDto(name="B", code="dup-uc"))


async def test_update_ad_link(ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    update = UpdateAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="Before", code="upd-1"))

    updated = await update(
        OWNER, UpdateAdLinkDto(ad_link_id=ad_link.id, name="After", cost=Decimal("25"))
    )

    assert updated.name == "After"
    assert updated.cost == Decimal("25")


async def test_delete_ad_link_without_attributions_succeeds(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    delete = DeleteAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="Del", code="del-1"))

    await delete(OWNER, ad_link.id)

    with pytest.raises(NotFoundError):
        await ad_link_repository.get_by_id(ad_link.id)


async def test_delete_ad_link_with_attributions_raises_validation_error(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    delete = DeleteAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="Keep", code="del-2"))
    user = await user_repository.create(CreateUserDto(name="Attr", telegram_id=930_001))
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.BOT
    )

    with pytest.raises(ValidationError):
        await delete(OWNER, ad_link.id)


async def test_list_ad_links_filters_by_is_active(
    ad_link_repository: AdLinkRepository, uow: UnitOfWork
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    update = UpdateAdLinkUseCase(ad_link_repository, uow)
    list_use_case = ListAdLinksUseCase(ad_link_repository, uow)
    active = await create(OWNER, CreateAdLinkDto(name="Active", code="list-active"))
    inactive = await create(OWNER, CreateAdLinkDto(name="Inactive", code="list-inactive"))
    await update(OWNER, UpdateAdLinkDto(ad_link_id=inactive.id, is_active=False))

    ad_links, total = await list_use_case(OWNER, ListAdLinksDto(is_active=True))

    codes = {link.code for link in ad_links}
    assert active.code in codes
    assert inactive.code not in codes
    assert total >= 1


async def test_generate_ad_link_code_returns_unused_code(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
) -> None:
    use_case = GenerateAdLinkCodeUseCase(ad_link_repository, uow)

    code = await use_case(OWNER)

    assert await ad_link_repository.get_by_code(code) is None
    assert len(code) == 12


def _paid_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreatePaymentOrderDto:
    return CreatePaymentOrderDto(
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
        customer_email=None,
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_get_ad_link_stats_zero_attributions_has_no_division_by_zero(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="Empty", code="stats-empty"))
    use_case = GetAdLinkStatsUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )

    stats = await use_case(OWNER, GetAdLinkStatsDto(ad_link_id=ad_link.id))

    assert stats.attributions_count == 0
    assert stats.conversion_rate == Decimal(0)
    assert stats.cpa is None


async def test_get_ad_link_stats_zero_cost_has_no_roi(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="Free", code="stats-free-cost"))
    user = await user_repository.create(CreateUserDto(name="Free User", telegram_id=940_001))
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.BOT
    )
    use_case = GetAdLinkStatsUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )

    stats = await use_case(OWNER, GetAdLinkStatsDto(ad_link_id=ad_link.id))

    assert stats.attributions_count == 1
    assert stats.cost == Decimal(0)
    assert stats.roi is None
    # attributed but nobody paid yet
    assert stats.cpa is None


async def test_get_ad_link_stats_computes_conversion_and_revenue(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(
        OWNER, CreateAdLinkDto(name="Paid Campaign", code="stats-paid", cost=Decimal("100"))
    )
    payer = await user_repository.create(CreateUserDto(name="Payer", telegram_id=940_002))
    non_payer = await user_repository.create(CreateUserDto(name="NonPayer", telegram_id=940_003))
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=payer.id, channel=AdLinkChannel.BOT
    )
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=non_payer.id, channel=AdLinkChannel.BOT
    )
    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="stats-paid-1")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    use_case = GetAdLinkStatsUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )
    stats = await use_case(
        OWNER, GetAdLinkStatsDto(ad_link_id=ad_link.id, report_currency=Currency.RUB)
    )

    assert stats.attributions_count == 2
    assert stats.paid_count == 1
    assert stats.conversion_rate == Decimal("0.5")
    assert stats.revenue == Decimal("500")
    assert stats.cost == Decimal("100")
    assert stats.roi == Decimal("4")
    assert stats.cpa == Decimal("100")


async def test_get_ad_link_stats_converts_revenue_with_a_non_unit_rate(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
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

    create = CreateAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="FX Campaign", code="stats-fx"))
    rub_payer = await user_repository.create(CreateUserDto(name="RubPayer", telegram_id=941_001))
    usd_payer = await user_repository.create(CreateUserDto(name="UsdPayer", telegram_id=941_002))
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=rub_payer.id, channel=AdLinkChannel.BOT
    )
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=usd_payer.id, channel=AdLinkChannel.BOT
    )
    async with uow:
        rub_order = await payment_order_repository.create(
            CreatePaymentOrderDto(
                **{
                    **_paid_order_dto(
                        user_id=rub_payer.id, plan_id=plan_id, idempotency_key="stats-fx-rub"
                    ).__dict__,
                    "currency": Currency.RUB,
                    "base_price": Decimal("900"),
                    "final_price": Decimal("900"),
                }
            )
        )
        usd_order = await payment_order_repository.create(
            CreatePaymentOrderDto(
                **{
                    **_paid_order_dto(
                        user_id=usd_payer.id, plan_id=plan_id, idempotency_key="stats-fx-usd"
                    ).__dict__,
                    "currency": Currency.USD,
                    "base_price": Decimal("5"),
                    "final_price": Decimal("5"),
                }
            )
        )
    await payment_order_repository.mark_status(rub_order.id, PaymentOrderStatus.PAID)
    await payment_order_repository.mark_status(usd_order.id, PaymentOrderStatus.PAID)

    use_case = GetAdLinkStatsUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )
    stats = await use_case(
        OWNER, GetAdLinkStatsDto(ad_link_id=ad_link.id, report_currency=Currency.USD)
    )

    # RUB 900 / 90 -> 10 USD, plus the 5 USD order.
    assert stats.report_currency == Currency.USD
    assert stats.revenue == Decimal("15")
    assert stats.revenue_by_currency == {
        Currency.RUB: Decimal("900"),
        Currency.USD: Decimal("5"),
    }


async def test_get_ad_link_stats_unknown_id_raises_not_found(
    ad_link_repository: AdLinkRepository,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> None:
    use_case = GetAdLinkStatsUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )

    with pytest.raises(NotFoundError):
        await use_case(OWNER, GetAdLinkStatsDto(ad_link_id=999_999))


async def test_list_ad_link_attributed_users_reports_paid_flag(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    payment_order_repository: PaymentOrderRepository,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="List", code="list-users"))
    payer = await user_repository.create(CreateUserDto(name="Payer2", telegram_id=940_004))
    non_payer = await user_repository.create(CreateUserDto(name="NonPayer2", telegram_id=940_005))
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=payer.id, channel=AdLinkChannel.BOT
    )
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=non_payer.id, channel=AdLinkChannel.WEBCABINET
    )
    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="list-users-1")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    use_case = ListAdLinkAttributedUsersUseCase(
        ad_link_repository, user_repository, payment_order_repository, uow
    )
    users, total = await use_case(OWNER, ListAdLinkAttributedUsersDto(ad_link_id=ad_link.id))

    assert total == 2
    by_id = {user.user_id: user for user in users}
    assert by_id[payer.id].has_paid is True
    assert by_id[non_payer.id].has_paid is False
    assert by_id[non_payer.id].channel == AdLinkChannel.WEBCABINET


async def test_list_ad_link_attributed_users_unknown_id_raises_not_found(
    ad_link_repository: AdLinkRepository,
    user_repository: UserRepository,
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ListAdLinkAttributedUsersUseCase(
        ad_link_repository, user_repository, payment_order_repository, uow
    )

    with pytest.raises(NotFoundError):
        await use_case(OWNER, ListAdLinkAttributedUsersDto(ad_link_id=999_999))


async def test_get_ad_link_stats_created_from_excludes_older_attributions(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="Period", code="stats-period"))
    user = await user_repository.create(CreateUserDto(name="Period User", telegram_id=942_001))
    await ad_link_repository.create_attribution(
        ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.BOT
    )
    use_case = GetAdLinkStatsUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )

    future = await use_case(
        OWNER,
        GetAdLinkStatsDto(ad_link_id=ad_link.id, created_from=datetime_now() + timedelta(days=1)),
    )
    past = await use_case(
        OWNER,
        GetAdLinkStatsDto(ad_link_id=ad_link.id, created_from=datetime_now() - timedelta(days=1)),
    )

    assert future.attributions_count == 0
    assert future.daily_registrations == []
    assert past.attributions_count == 1


async def test_get_advertising_summary_aggregates_links(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    paid_link = await create(
        OWNER, CreateAdLinkDto(name="Paid", code="summary-paid", cost=Decimal("100"))
    )
    free_link = await create(OWNER, CreateAdLinkDto(name="Free", code="summary-free"))
    payer = await user_repository.create(CreateUserDto(name="Payer", telegram_id=943_001))
    non_payer = await user_repository.create(CreateUserDto(name="NonPayer", telegram_id=943_002))
    web_user = await user_repository.create(CreateUserDto(name="Web", telegram_id=943_003))
    await ad_link_repository.create_attribution(
        ad_link_id=paid_link.id, user_id=payer.id, channel=AdLinkChannel.BOT
    )
    await ad_link_repository.create_attribution(
        ad_link_id=paid_link.id, user_id=non_payer.id, channel=AdLinkChannel.BOT
    )
    await ad_link_repository.create_attribution(
        ad_link_id=free_link.id, user_id=web_user.id, channel=AdLinkChannel.WEBCABINET
    )
    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="summary-paid-1")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    use_case = GetAdvertisingSummaryUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )
    summary = await use_case(OWNER, GetAdvertisingSummaryDto(report_currency=Currency.RUB))

    assert summary.attributions_count == 3
    assert summary.attributions_by_channel == {
        AdLinkChannel.BOT: 2,
        AdLinkChannel.WEBCABINET: 1,
    }
    assert summary.paid_count == 1
    assert summary.revenue == Decimal("500")
    assert summary.cost == Decimal("100")
    assert summary.roi == Decimal("4")
    assert summary.cpa == Decimal("100")
    metrics = {link.ad_link_id: link for link in summary.links}
    assert metrics[paid_link.id].attributions_count == 2
    assert metrics[paid_link.id].paid_count == 1
    assert metrics[paid_link.id].roi == Decimal("4")
    assert metrics[free_link.id].attributions_count == 1
    assert metrics[free_link.id].roi is None

    inactive_only = await use_case(OWNER, GetAdvertisingSummaryDto(is_active=False))
    assert inactive_only.links == []
    assert inactive_only.cpa is None


async def test_regular_user_cannot_get_advertising_summary(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
) -> None:
    use_case = GetAdvertisingSummaryUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )
    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, GetAdvertisingSummaryDto())


async def test_get_advertising_summary_created_to_is_a_snapshot(
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    session: AsyncSession,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
    plan_id: int,
) -> None:
    create = CreateAdLinkUseCase(ad_link_repository, uow)
    ad_link = await create(OWNER, CreateAdLinkDto(name="Snapshot", code="summary-snapshot"))
    old = await user_repository.create(CreateUserDto(name="Old", telegram_id=944_001))
    new = await user_repository.create(CreateUserDto(name="New", telegram_id=944_002))
    for user in (old, new):
        await ad_link_repository.create_attribution(
            ad_link_id=ad_link.id, user_id=user.id, channel=AdLinkChannel.BOT
        )
    await session.execute(
        update(AdLinkAttribution)
        .where(AdLinkAttribution.user_id == old.id)
        .values(created_at=datetime_now() - timedelta(days=10))
    )
    # attributed before the snapshot, paid after it
    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=old.id, plan_id=plan_id, idempotency_key="summary-snapshot-1")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)
    use_case = GetAdvertisingSummaryUseCase(
        ad_link_repository, payment_order_repository, pricing_repository, uow
    )

    snapshot = await use_case(
        OWNER,
        GetAdvertisingSummaryDto(
            report_currency=Currency.RUB, created_to=datetime_now() - timedelta(days=1)
        ),
    )
    live = await use_case(OWNER, GetAdvertisingSummaryDto(report_currency=Currency.RUB))

    assert snapshot.attributions_count == 1
    assert snapshot.paid_count == 0
    assert snapshot.revenue == Decimal("0")
    assert live.attributions_count == 2
    assert live.paid_count == 1
