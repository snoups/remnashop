from dataclasses import dataclass, field
from typing import ClassVar

from app.core.enums import Currency, PriceAdjustScope
from app.core.events import EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class CurrencyRateChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PRICING
    currency: Currency
    old_rate: str
    new_rate: str


@dataclass(frozen=True, kw_only=True)
class AnchorSwitchedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PRICING
    old_anchor: Currency
    new_anchor: Currency


@dataclass(frozen=True, kw_only=True)
class BasePricesAdjustedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PRICING
    scope: PriceAdjustScope
    factor: str


@dataclass(frozen=True, kw_only=True)
class PricingSettingsChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PRICING
    changed_fields: list[str] = field(default_factory=list)
