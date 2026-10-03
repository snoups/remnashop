from dataclasses import dataclass, field
from typing import ClassVar, Optional

from app.core.events import EventCategory, UserEvent


@dataclass(frozen=True, kw_only=True)
class GatewayChangedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    action: str
    gateway_type: Optional[str] = None
    # names only, these are merchant credentials
    changed_fields: list[str] = field(default_factory=list)
    is_active: Optional[bool] = None
