from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import GiveawayCampaignStatus, GiveawayEntryStatus, PurchaseType

from .base import BaseSql
from .timestamp import TimestampMixin
from .user import User


class GiveawayCampaign(BaseSql, TimestampMixin):
    __tablename__ = "giveaway_campaigns"
    __table_args__ = (
        CheckConstraint("winner_count > 0", name="ck_giveaway_campaign_winner_count"),
        CheckConstraint("prize_amount >= 0", name="ck_giveaway_campaign_prize_amount"),
        CheckConstraint("ends_at > starts_at", name="ck_giveaway_campaign_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[GiveawayCampaignStatus] = mapped_column(index=True)
    starts_at: Mapped[datetime] = mapped_column(index=True)
    ends_at: Mapped[datetime] = mapped_column(index=True)
    winner_count: Mapped[int]
    prize_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    eligible_plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        index=True,
    )
    eligible_duration_days: Mapped[int]
    eligible_purchase_types: Mapped[list[str]] = mapped_column(JSONB)
    code_prefix: Mapped[str] = mapped_column(String(8), default="VAY")
    completed_at: Mapped[Optional[datetime]]
    archived_at: Mapped[Optional[datetime]]

    entries: Mapped[list["GiveawayEntry"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class GiveawayEntry(BaseSql, TimestampMixin):
    __tablename__ = "giveaway_entries"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "participant_code",
            name="uq_giveaway_entry_campaign_code",
        ),
        UniqueConstraint(
            "campaign_id",
            "winner_rank",
            name="uq_giveaway_entry_campaign_winner_rank",
        ),
        UniqueConstraint(
            "transaction_payment_id",
            name="uq_giveaway_entry_transaction_payment",
        ),
        CheckConstraint(
            "winner_rank IS NULL OR winner_rank > 0",
            name="ck_giveaway_entry_winner_rank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("giveaway_campaigns.id", ondelete="CASCADE"),
        index=True,
    )
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        index=True,
    )
    telegram_username: Mapped[Optional[str]] = mapped_column(String(32))
    participant_code: Mapped[str] = mapped_column(String(32))
    transaction_payment_id: Mapped[UUID] = mapped_column(index=True)
    plan_id: Mapped[int]
    plan_name: Mapped[str] = mapped_column(String(128))
    duration_days: Mapped[int]
    purchase_type: Mapped[PurchaseType]
    phone: Mapped[Optional[str]] = mapped_column(String(15))
    status: Mapped[GiveawayEntryStatus] = mapped_column(index=True)
    winner_rank: Mapped[Optional[int]]
    selected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    campaign: Mapped["GiveawayCampaign"] = relationship(back_populates="entries")
    user: Mapped["User"] = relationship(foreign_keys=[user_telegram_id])
