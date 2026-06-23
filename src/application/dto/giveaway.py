from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.core.enums import (
    GiveawayCampaignStatus,
    GiveawayEntrySource,
    GiveawayEntryStatus,
    PurchaseType,
)

from .base import BaseDto, TimestampMixin, TrackableMixin


@dataclass(kw_only=True)
class GiveawayCampaignDto(BaseDto, TrackableMixin, TimestampMixin):
    name: str
    status: GiveawayCampaignStatus
    starts_at: datetime
    ends_at: datetime
    winner_count: int
    prize_amount: Decimal
    eligible_plan_id: int
    eligible_duration_days: int
    eligible_purchase_types: list[PurchaseType] = field(default_factory=list)
    code_prefix: str = "VAY"
    rules_text: Optional[str] = None
    completed_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None


@dataclass(kw_only=True)
class GiveawayEntryDto(BaseDto, TrackableMixin, TimestampMixin):
    campaign_id: int
    user_telegram_id: Optional[int]
    telegram_username: Optional[str]
    participant_code: str
    transaction_payment_id: Optional[UUID]
    plan_id: int
    plan_name: str
    duration_days: int
    purchase_type: Optional[PurchaseType]
    entry_source: GiveawayEntrySource = GiveawayEntrySource.AUTO_PURCHASE
    phone: Optional[str] = None
    status: GiveawayEntryStatus = GiveawayEntryStatus.ELIGIBLE
    winner_rank: Optional[int] = None
    selected_at: Optional[datetime] = None


@dataclass(frozen=True)
class ClientGiveawayDto:
    campaign: GiveawayCampaignDto
    plan_name: str
    entry: Optional[GiveawayEntryDto] = None
