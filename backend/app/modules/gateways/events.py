from dataclasses import dataclass, field
from typing import ClassVar, Literal, Optional

from app.core.enums import PaymentGatewayType
from app.core.events import ActorEvent, EventCategory


@dataclass(frozen=True, kw_only=True)
class GatewayChangedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    action: Literal["disable", "enable", "reorder", "settings"]
    gateway_type: Optional[PaymentGatewayType] = None
    # names only, these are merchant credentials
    changed_fields: list[str] = field(default_factory=list)
    is_active: Optional[bool] = None
