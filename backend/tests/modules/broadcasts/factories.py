from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count
from typing import Any, Final, Optional
from uuid import uuid4

import httpx
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import DeleteMessage, GetMe, TelegramMethod
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.subscription import Subscription
from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    PurchaseChannel,
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
            channel=PurchaseChannel.CABINET,
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


class _ResponderSession(BaseSession):
    """Answers each call with the responder's raw Bot API reply, which aiogram
    then parses (or turns into its exception) exactly as for a real response."""

    def __init__(self, telegram: "MockTelegram") -> None:
        super().__init__()
        self._telegram = telegram

    async def make_request(
        self, bot: Bot, method: TelegramMethod[Any], timeout: Optional[int] = None
    ) -> Any:
        self._telegram.requests.append(method)
        reply = self._telegram.responder(method)
        response = self.check_response(
            bot=bot, method=method, status_code=reply.status_code, content=reply.text
        )
        return response.result

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        raise AssertionError("broadcasts never download")
        yield b""

    async def close(self) -> None:
        pass


class MockTelegram(TelegramClientFactory):
    def __init__(self, responder: Callable[[TelegramMethod[Any]], httpx.Response]) -> None:
        self.requests: list[TelegramMethod[Any]] = []
        self.responder = responder

    @asynccontextmanager
    async def _bot(self, token: str) -> AsyncIterator[Bot]:
        yield Bot(token=token, session=_ResponderSession(self))

    def open(self, token: str, proxy: Optional[str]) -> AbstractAsyncContextManager[Bot]:
        return self._bot(token)


def message_result(message_id: int = 100, **extra: Any) -> dict[str, Any]:
    return {"message_id": message_id, "date": 0, "chat": {"id": 1, "type": "private"}, **extra}


BOT_USER: Final[dict[str, Any]] = {
    "id": 123,
    "is_bot": True,
    "first_name": "bot",
    "username": "shop_bot",
}


def ok_response(method: TelegramMethod[Any]) -> httpx.Response:
    result: object = message_result()
    if isinstance(method, DeleteMessage):
        result = True
    elif isinstance(method, GetMe):
        result = BOT_USER
    return httpx.Response(200, json={"ok": True, "result": result})
