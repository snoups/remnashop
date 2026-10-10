from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Protocol, runtime_checkable

from app.core.enums import Locale
from app.core.events import BaseEvent


@runtime_checkable
class EventPublisher(Protocol):
    async def publish(self, event: BaseEvent) -> None: ...


class OidcIdentityCleaner(Protocol):
    async def delete_all_oidc(self) -> int: ...


class OutboxEntryDispatch(Protocol):
    async def kiq(self, *, outbox_id: int) -> object: ...


@runtime_checkable
class SessionRevoker(Protocol):
    async def revoke_all_by_user(self, user_id: int) -> None: ...


@runtime_checkable
class SubscriptionRevoker(Protocol):
    async def revoke_all_by_user(self, user_id: int) -> None: ...


@runtime_checkable
class ReferrerLookup(Protocol):
    async def has_referrer(self, user_id: int) -> bool: ...


class PlanReferenceCleaner(Protocol):
    async def forget_plan(self, plan_id: int) -> None: ...


class PromocodeLiveness(Protocol):
    async def is_live(self, promocode_id: int) -> bool: ...


class AnchorAmountRescaler(Protocol):
    async def rescale_anchor_amounts(self, factor: Decimal) -> None: ...


@dataclass(frozen=True, kw_only=True)
class SpentPurchaseDiscount:
    user_id: int
    percent: int
    promocode_id: Optional[int]
    from_promocode: bool


class OrderFailer(Protocol):
    async def fail_unpaid_free_order(self, idempotency_key: str) -> Optional[SpentPurchaseDiscount]:
        """The one-shot discount to hand back when this call failed the order."""
        ...


class OpenOrderCounter(Protocol):
    # NEW orders that can still become a subscription: unexpired PENDING or PAID-unlinked
    async def count_open_new_orders(
        self, user_id: int, now: datetime, *, exclude_key: Optional[str] = None
    ) -> int: ...


class LoyaltyThresholdRescaler(Protocol):
    async def rescale_thresholds(self, factor: Decimal) -> None: ...


@runtime_checkable
class PasskeyRevoker(Protocol):
    async def delete_all_by_user(self, user_id: int) -> int: ...


class BotSignals(Protocol):
    # tells a running telegram process to pick up a change made elsewhere
    async def restart(self) -> None: ...

    async def dialogs_changed(self) -> None: ...

    async def translation_changed(
        self, locale: Locale, message_id: str, attribute_id: str, value: str
    ) -> None: ...


class DefaultBannerSeed(Protocol):
    # puts the shipped banner in place for a locale that has none
    async def ensure(self, locale: Locale) -> None: ...


class BotCommandsSync(Protocol):
    # re-sends the bot's command menu after a translation or locale change;
    # both are no-ops while no bot is configured, push() is False on failure
    async def push(self) -> bool: ...

    async def drop_locale(self, locale: Locale) -> None: ...


@runtime_checkable
class TranslatorRunner(Protocol):
    def get(self, key: str, obj: Any = None, **kwargs: Any) -> str: ...

    def from_event(self, event: Any, **kwargs: Any) -> str: ...

    def __call__(self, obj: Any = None, **kwargs: Any) -> str: ...

    def __getattr__(self, item: str) -> "TranslatorRunner": ...


@runtime_checkable
class TranslatorHub(Protocol):
    def get_translator_by_locale(self, locale: str) -> TranslatorRunner: ...
