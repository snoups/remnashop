from collections.abc import Awaitable
from dataclasses import dataclass
from enum import auto
from typing import Any, Optional, TypeVar

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import UpperStrEnum
from app.core.exceptions import NotFoundError
from app.modules.promocodes import PromocodeDto, PromocodeRepository
from app.modules.settings import AccessSettingsDto, SettingsRepository
from app.modules.subscriptions import PanelTrafficUsage, SubscriptionDto, SubscriptionRepository
from app.modules.transactions import TransactionDto, TransactionRepository
from app.modules.users import UserDto, UserRepository

_T = TypeVar("_T")


async def _find(lookup: Awaitable[_T]) -> Optional[_T]:
    try:
        return await lookup
    except NotFoundError:
        return None


class CardSection(UpperStrEnum):
    PAYMENT = auto()
    SUBSCRIPTION = auto()
    PLAN = auto()
    PROMOCODE = auto()
    DEVICE = auto()
    BUILD = auto()
    ACCESS = auto()


@dataclass(frozen=True, kw_only=True)
class CardData:
    """What a card shows beyond the event payload, looked up once per event."""

    user: Optional[UserDto] = None
    order: Optional[TransactionDto] = None
    subscription: Optional[SubscriptionDto] = None
    used_traffic: Optional[int] = None
    promocode: Optional[PromocodeDto] = None
    access: Optional[AccessSettingsDto] = None


def _int(payload: dict[str, Any], key: str) -> Optional[int]:
    value = payload.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class TelegramCardDataLoader:
    def __init__(
        self,
        uow: UnitOfWork,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository,
        transaction_repository: TransactionRepository,
        promocode_repository: PromocodeRepository,
        settings_repository: SettingsRepository,
        usage: PanelTrafficUsage,
    ) -> None:
        self._uow = uow
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._transaction_repository = transaction_repository
        self._promocode_repository = promocode_repository
        self._settings_repository = settings_repository
        self._usage = usage

    async def load(
        self, sections: frozenset[CardSection], payload: dict[str, Any], *, load_user: bool
    ) -> CardData:
        # a card without its extra blocks still beats no card
        try:
            return await self._load(sections, payload, load_user=load_user)
        except Exception:
            logger.exception("Telegram card data lookup failed")
            return CardData()

    async def _load(
        self, sections: frozenset[CardSection], payload: dict[str, Any], *, load_user: bool
    ) -> CardData:
        user = order = subscription = promocode = access = None
        async with self._uow:
            user_id = _int(payload, "user_id")
            if load_user and user_id is not None:
                user = await self._user_repository.find_by_id(user_id)
            order_id = _int(payload, "order_id")
            payment_key = payload.get("payment_key")
            if order_id is not None:
                order = await _find(self._transaction_repository.get_by_id(order_id))
            elif CardSection.PAYMENT in sections and isinstance(payment_key, str):
                order = await self._transaction_repository.find_by_idempotency_key(payment_key)
            if sections & {CardSection.SUBSCRIPTION, CardSection.PLAN}:
                subscription_id = _int(payload, "subscription_id") or (
                    order.fulfilled_subscription_id if order is not None else None
                )
                if subscription_id is not None:
                    subscription = await _find(
                        self._subscription_repository.get_by_id(subscription_id)
                    )
            promocode_id = _int(payload, "promocode_id")
            if CardSection.PROMOCODE in sections and promocode_id is not None:
                promocode = await _find(self._promocode_repository.get_by_id(promocode_id))
            if CardSection.ACCESS in sections:
                access = await self._settings_repository.get_access_settings()
        used_traffic = None
        if CardSection.SUBSCRIPTION in sections and subscription is not None:
            # outside the transaction: a slow panel mustn't hold a connection
            used_traffic = await self._usage.used_traffic(subscription)
        return CardData(
            user=user,
            order=order,
            subscription=subscription,
            used_traffic=used_traffic,
            promocode=promocode,
            access=access,
        )
