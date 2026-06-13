from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.core.enums import PromoAudience

from .base import BaseDto, TimestampMixin, TrackableMixin
from .plan import PlanDto


@dataclass(kw_only=True)
class PromocodeDto(BaseDto, TrackableMixin, TimestampMixin):
    code: str
    discount_percent: int
    plan_id: int
    audience: PromoAudience
    max_activations: int
    expires_at: datetime
    is_active: bool

    plan: Optional[PlanDto] = field(default=None)


@dataclass(kw_only=True)
class PromocodeActivationDto(BaseDto, TrackableMixin):
    promocode_id: int
    user_telegram_id: int
    transaction_payment_id: UUID
    activated_at: Optional[datetime] = field(default=None)
