from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentOutcome, PurchaseChannel
from app.modules.customer_notifications.dto import ShowPaymentCanceledDto
from app.modules.customer_notifications.usecases import ShowPaymentCanceledUseCase
from app.modules.transactions import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.customer_notifications.factories import FakeBotSignals, create_order


class _Fixture:
    def __init__(self, users: UserRepository, orders: TransactionRepository, uow: UnitOfWork):
        self.users = users
        self.orders = orders
        self.uow = uow
        self.signals = FakeBotSignals()
        self.use_case = ShowPaymentCanceledUseCase(orders, users, cast(Any, self.signals), uow)

    async def create_user(self, bot_blocked: bool = False, **fields: Any) -> UserDto:
        async with self.uow:
            user = await self.users.create(CreateUserDto(**fields))
            if bot_blocked:
                await self.users.set_bot_blocked(user.id, True)
            await self.uow.commit()
        return user

    async def order(self, user: UserDto, channel: PurchaseChannel, key: str) -> int:
        order = await create_order(self.orders, self.uow, user_id=user.id, channel=channel, key=key)
        return order.id

    async def cancel(self, order_id: int) -> None:
        await self.use_case.system(ShowPaymentCanceledDto(order_id=order_id))


@pytest.fixture
def fx(user_repository: UserRepository, session: AsyncSession, uow: UnitOfWork) -> _Fixture:
    return _Fixture(user_repository, TransactionRepository(session), uow)


async def test_cancel_shows_window_for_latest_bot_order(fx: _Fixture) -> None:
    user = await fx.create_user(name="a", telegram_id=8101)
    order_id = await fx.order(user, PurchaseChannel.BOT, "cancel-1")

    await fx.cancel(order_id)

    assert fx.signals.outcomes == [(8101, order_id, PaymentOutcome.CANCELED)]


async def test_cancel_skipped_when_newer_bot_order_exists(fx: _Fixture) -> None:
    user = await fx.create_user(name="a", telegram_id=8102)
    order_id = await fx.order(user, PurchaseChannel.BOT, "cancel-2a")
    await fx.order(user, PurchaseChannel.BOT, "cancel-2b")

    await fx.cancel(order_id)

    assert fx.signals.outcomes == []


async def test_cancel_skipped_for_cabinet_order(fx: _Fixture) -> None:
    user = await fx.create_user(name="a", telegram_id=8103)
    order_id = await fx.order(user, PurchaseChannel.CABINET, "cancel-3")

    await fx.cancel(order_id)

    assert fx.signals.outcomes == []


@pytest.mark.parametrize(
    "fields",
    [
        {"email": "a@example.com"},
        {"telegram_id": 8104, "bot_blocked": True},
        {"telegram_id": 8105, "is_blocked": True},
    ],
)
async def test_cancel_skipped_without_telegram(fx: _Fixture, fields: dict[str, Any]) -> None:
    user = await fx.create_user(name="a", **fields)
    order_id = await fx.order(user, PurchaseChannel.BOT, "cancel-4")

    await fx.cancel(order_id)

    assert fx.signals.outcomes == []
