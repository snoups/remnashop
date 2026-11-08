from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from remnapy.enums import TrafficLimitStrategy

from app.core.enums import Currency


# outside api/: transactions returns it too, and subscriptions.api would pull in the routers
class PlanSnapshotResponse(BaseModel):
    plan_id: int
    public_code: str
    name: str
    price_paid: Decimal
    currency: Currency
    duration_days: int
    traffic_limit: int
    device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy
    is_trial: bool
    internal_squads: list[UUID]
    external_squad: Optional[UUID] = None
    tag: Optional[str] = None
    # None on a snapshot written before they existed
    credit_paid: Optional[Decimal] = None
    credit_days: Optional[int] = None
