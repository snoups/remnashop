import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PaymentGatewayType, TransactionStatus
from app.modules.gateways.repository import GatewayRepository
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases import ListPaymentMethodsUseCase
from app.modules.users import UserRepository
from app.modules.users.dto import CreateUserDto, UserDto
from tests.modules.transactions.test_repository import _order_dto


@pytest.fixture
def use_case(
    gateway_repository: GatewayRepository,
    transaction_repository: TransactionRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> ListPaymentMethodsUseCase:
    return ListPaymentMethodsUseCase(
        gateway_repository, transaction_repository, settings_repository, uow
    )


@pytest.fixture
async def actor(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(CreateUserDto(name="buyer", telegram_id=700_101))


async def _activate_yookassa(
    gateway_repository: GatewayRepository, uow: UnitOfWork, **extra: str
) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.YOOKASSA, {"shop_id": "1", "api_key": "k", **extra}
        )
        await gateway_repository.set_active(PaymentGatewayType.YOOKASSA, True)


@pytest.fixture
async def active_yookassa(gateway_repository: GatewayRepository, uow: UnitOfWork) -> None:
    await _activate_yookassa(gateway_repository, uow)


@pytest.fixture
async def receipt_yookassa(gateway_repository: GatewayRepository, uow: UnitOfWork) -> None:
    await _activate_yookassa(gateway_repository, uow, vat_code="1")


@pytest.fixture
async def active_stars_paid_only(gateway_repository: GatewayRepository, uow: UnitOfWork) -> None:
    async with uow:
        await gateway_repository.update_settings(
            PaymentGatewayType.TELEGRAM_STARS, {"require_paid_purchase": "true"}
        )
        await gateway_repository.set_active(PaymentGatewayType.TELEGRAM_STARS, True)


@pytest.fixture
async def paid_yookassa_order(
    transaction_repository: TransactionRepository, uow: UnitOfWork, actor: UserDto, plan_id: int
) -> None:
    async with uow:
        created = await transaction_repository.create(
            _order_dto(user_id=actor.id, plan_id=plan_id, idempotency_key="paid-order")
        )
        await transaction_repository.mark_status(created.id, TransactionStatus.PAID)


async def test_lists_only_active_configured_gateways(
    use_case: ListPaymentMethodsUseCase, actor: UserDto, active_yookassa: None
) -> None:
    methods = await use_case(actor)

    assert [m.gateway_type for m in methods] == [PaymentGatewayType.YOOKASSA]
    assert methods[0].currency is Currency.RUB
    assert methods[0].requires_email is False


async def test_flags_a_gateway_that_needs_an_email(
    use_case: ListPaymentMethodsUseCase, actor: UserDto, receipt_yookassa: None
) -> None:
    methods = await use_case(actor)

    assert [(m.gateway_type, m.requires_email) for m in methods] == [
        (PaymentGatewayType.YOOKASSA, True)
    ]


async def test_shop_payment_email_means_no_email_is_asked(
    use_case: ListPaymentMethodsUseCase,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    actor: UserDto,
    receipt_yookassa: None,
) -> None:
    async with uow:
        await settings_repository.update_shop_settings(
            UpdateShopSettingsDto(
                payment_email="owner@shop.example", fields_set=frozenset({"payment_email"})
            )
        )

    assert [(m.requires_email, m.asks_email) for m in await use_case(actor)] == [(False, False)]


async def test_stars_hidden_until_a_paid_purchase(
    use_case: ListPaymentMethodsUseCase, actor: UserDto, active_stars_paid_only: None
) -> None:
    assert await use_case(actor) == []


async def test_stars_shown_after_a_paid_purchase(
    use_case: ListPaymentMethodsUseCase,
    actor: UserDto,
    active_stars_paid_only: None,
    paid_yookassa_order: None,
) -> None:
    assert [m.gateway_type for m in await use_case(actor)] == [PaymentGatewayType.TELEGRAM_STARS]
