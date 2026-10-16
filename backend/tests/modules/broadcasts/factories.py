from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count
from typing import Any, Final, Optional
from uuid import uuid4

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.subscription import Subscription
from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.broadcasts.telegram_api import TelegramClientFactory
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

_remnawave_ids = count(900_000)
_TX_LIFETIME: Final[timedelta] = timedelta(hours=1)


async def make_customer(
    user_repository: UserRepository,
    session: AsyncSession,
    *,
    telegram_id: Optional[int],
    language: Locale = Locale.EN,
    **fields: Any,
) -> int:
    user = await user_repository.create(
        CreateUserDto(name=f"c{telegram_id}", telegram_id=telegram_id, language=language)
    )
    if fields:
        await session.execute(update(User).where(User.id == user.id).values(**fields))
    return user.id


async def add_subscription(
    session: AsyncSession,
    user_id: int,
    *,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    is_trial: bool = False,
    plan_id: int = 1,
    plan_name: str = "Basic",
    expire_at: Optional[datetime] = None,
    first_connected_at: Optional[datetime] = None,
    created_at: Optional[datetime] = None,
) -> None:
    snapshot = make_plan_snapshot(plan_id=plan_id, name=plan_name, is_trial=is_trial)
    # an explicit None would bypass the server default
    extra: dict[str, Any] = {"created_at": created_at} if created_at is not None else {}
    session.add(
        Subscription(
            user_id=user_id,
            remnawave_user_id=next(_remnawave_ids),
            status=status,
            is_trial=is_trial,
            traffic_limit=100,
            device_limit=3,
            traffic_limit_strategy=snapshot.traffic_limit_strategy,
            internal_squads=[],
            expire_at=expire_at or datetime_now() + timedelta(days=30),
            url="https://example.com/sub",
            plan_snapshot=snapshot.to_json(),
            first_connected_at=first_connected_at,
            **extra,
        )
    )
    await session.flush()


async def add_paid_transaction(session: AsyncSession, user_id: int) -> None:
    snapshot = make_plan_snapshot()
    price = Decimal("100")
    session.add(
        Transaction(
            user_id=user_id,
            plan_snapshot=snapshot.to_json(),
            duration_days=snapshot.duration_days,
            currency=Currency.RUB,
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.YOOKASSA,
            status=TransactionStatus.PAID,
            base_price=price,
            final_price=price,
            anchor_base_price=price,
            anchor_final_price=price,
            idempotency_key=str(uuid4()),
            expires_at=datetime_now() + _TX_LIFETIME,
            is_test=False,
        )
    )
    await session.flush()


class MockTelegram(TelegramClientFactory):
    def __init__(self, responder: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []
        self._responder = responder

    def open(self, proxy: Optional[str]) -> httpx.AsyncClient:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self._responder(request)

        return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": {"message_id": 100}})
