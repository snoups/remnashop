from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import CurrencyRate, PricingSettings, Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    Role,
)
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.utils.time import datetime_now
from app.modules.pricing import PricingRepository
from app.modules.transactions.dto import (
    CreateTransactionDto,
    RateUnratedAnchorAmountsDto,
    TransactionDto,
    UnratedAnchorCountDto,
)
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import (
    ListUnratedAnchorAmountsUseCase,
    RateUnratedAnchorAmountsUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(name="owner", role=Role.OWNER)
ADMIN = UserDto(name="admin", role=Role.ADMIN)


async def _order(
    repository: TransactionRepository,
    session: AsyncSession,
    user_id: int,
    currency: Currency,
    price: Decimal,
    *,
    unrated: bool,
) -> TransactionDto:
    order = await repository.create(
        CreateTransactionDto(
            channel=PurchaseChannel.BOT,
            user_id=user_id,
            plan_id=None,
            plan_snapshot=make_plan_snapshot(),
            duration_days=30,
            currency=currency,
            purchase_type=PurchaseType.NEW,
            target_subscription_id=None,
            gateway_type=PaymentGatewayType.YOOKASSA,
            base_price=price * 2,
            discount_percent=50,
            discount_source=DiscountSource.PERSONAL,
            final_price=price,
            anchor_base_price=price * 2,
            anchor_final_price=price,
            customer_email=None,
            idempotency_key=uuid4().hex,
            expires_at=datetime_now(),
        )
    )
    await session.execute(
        update(Transaction)
        .where(Transaction.id == order.id)
        .values(anchor_unrated=unrated, updated_at=datetime_now() - timedelta(days=40))
    )
    return await repository.get_by_id(order.id)


async def test_rate_converts_only_unrated_amounts_at_current_rates(
    session: AsyncSession,
    user_repository: UserRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    repository = TransactionRepository(session)
    await pricing_repository.get_rate_table()
    await session.execute(update(PricingSettings).values(anchor_currency=Currency.USD))
    await session.execute(
        update(CurrencyRate).where(CurrencyRate.currency == Currency.USD).values(rate=1)
    )
    await session.execute(
        update(CurrencyRate).where(CurrencyRate.currency == Currency.RUB).values(rate=85)
    )
    session.expire_all()
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=950_101))
    rub = await _order(repository, session, buyer.id, Currency.RUB, Decimal("850"), unrated=True)
    usd = await _order(repository, session, buyer.id, Currency.USD, Decimal("5"), unrated=True)
    rated = await _order(repository, session, buyer.id, Currency.RUB, Decimal("850"), unrated=False)

    listed = await ListUnratedAnchorAmountsUseCase(repository, uow)(OWNER)
    assert listed == [
        UnratedAnchorCountDto(currency=Currency.RUB, count=1),
        UnratedAnchorCountDto(currency=Currency.USD, count=1),
    ]

    remaining = await RateUnratedAnchorAmountsUseCase(
        repository, pricing_repository, uow, event_publisher
    )(OWNER, RateUnratedAnchorAmountsDto(client_ip="127.0.0.1"))

    assert remaining == []
    session.expire_all()
    after_rub = await repository.get_by_id(rub.id)
    assert (after_rub.anchor_base_price, after_rub.anchor_final_price) == (
        Decimal("20.00"),
        Decimal("10.00"),
    )
    assert after_rub.updated_at == rub.updated_at
    after_usd = await repository.get_by_id(usd.id)
    assert after_usd.anchor_final_price == Decimal("5")
    # amounts converted at checkout are left alone
    assert (await repository.get_by_id(rated.id)).anchor_final_price == Decimal("850")
    assert await repository.count_unrated_anchor_amounts() == {}


def test_rating_is_owner_only_and_viewing_is_an_admin_default() -> None:
    assert RateUnratedAnchorAmountsUseCase.required_permission is (
        Permission.TRANSACTIONS_UNRATED_RATE
    )
    assert ListUnratedAnchorAmountsUseCase.required_permission is (
        Permission.TRANSACTIONS_UNRATED_VIEW
    )
    assert not PermissionPolicy.has_permission(ADMIN, Permission.TRANSACTIONS_UNRATED_RATE)
    assert PermissionPolicy.has_permission(ADMIN, Permission.TRANSACTIONS_UNRATED_VIEW)
