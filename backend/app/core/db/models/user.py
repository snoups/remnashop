from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Locale, Role
from app.core.utils.email import canonical_email


class User(BaseSql, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        # Only one OWNER may ever exist; the app-level check in BootstrapOwnerUseCase
        # is TOCTOU-racy on its own, so this is the actual guarantee.
        Index(
            "ux_users_single_owner",
            "role",
            unique=True,
            postgresql_where=text(f"role = '{Role.OWNER.name}'"),
        ),
        # newest-first user list, registrations per period
        Index("ix_users_created_at_id", text("created_at DESC"), text("id DESC")),
        # LOGIN_PATTERN (app/core/constants.py) at the DB level, which also
        # covers rows the API didn't write
        CheckConstraint(
            "login IS NULL OR login ~ '^[A-Za-z0-9._-]+$'",
            name="ck_users_login_charset",
        ),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        CheckConstraint(
            "personal_discount BETWEEN 0 AND 100", name="ck_users_personal_discount_range"
        ),
        CheckConstraint(
            "purchase_discount BETWEEN 0 AND 100", name="ck_users_purchase_discount_range"
        ),
        CheckConstraint(
            "loyalty_discount BETWEEN 0 AND 100", name="ck_users_loyalty_discount_range"
        ),
        CheckConstraint("points >= 0", name="ck_users_points_non_negative"),
        CheckConstraint("bonus_days >= 0", name="ck_users_bonus_days_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(32), index=True)

    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    email_canonical: Mapped[Optional[str]] = mapped_column(String(255), index=True, unique=True)
    login: Mapped[Optional[str]] = mapped_column(String(64), index=True, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(161))

    name: Mapped[str] = mapped_column(String())
    role: Mapped[Role] = mapped_column(index=True)
    language: Mapped[Locale]

    is_blocked: Mapped[bool]
    # set when someone else generated the password; cleared by the user's own change
    password_change_required: Mapped[bool] = mapped_column(default=False, server_default="false")

    permission_grants: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    permission_revokes: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    ip_allowlist: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    personal_discount: Mapped[int] = mapped_column(default=0, server_default="0")
    purchase_discount: Mapped[int] = mapped_column(default=0, server_default="0")
    # the promocode that set each discount; NULL when an admin set it or it's 0
    personal_discount_promocode_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("promocodes.id", ondelete="SET NULL"), index=True
    )
    purchase_discount_promocode_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("promocodes.id", ondelete="SET NULL"), index=True
    )
    loyalty_discount: Mapped[int] = mapped_column(default=0, server_default="0")
    loyalty_excluded: Mapped[bool] = mapped_column(default=False, server_default="false")
    marketing_opt_out: Mapped[bool] = mapped_column(default=False, server_default="false")
    # set by a refused send or a "kicked" chat-member update, cleared by any message to the bot
    is_bot_blocked: Mapped[bool] = mapped_column(default=False, server_default="false")
    email_undeliverable_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # NULL = never accepted; a date, not a flag, so changed rules can ask again
    # create() always generates one, a soft delete wipes it
    referral_code: Mapped[Optional[str]] = mapped_column(String(16), unique=True, index=True)
    points: Mapped[Decimal] = mapped_column(Numeric(12, 0), default=Decimal(0), server_default="0")
    bonus_days: Mapped[int] = mapped_column(default=0, server_default="0")
    # One-way latch: True until the first trial activation. Not derived from
    # history: a trial->paid conversion marks the trial row DELETED
    # (NewPurchase._upgrade_trial_in_place).
    is_trial_available: Mapped[bool] = mapped_column(default=True, server_default="true")
    # dashboard bell: events up to this moment count as read
    notifications_seen_at: Mapped[Optional[datetime]]
    # dashboard bell: events up to this moment are hidden from it (the event log keeps them)
    notifications_cleared_at: Mapped[Optional[datetime]]
    # {group: [channel, ...]}; NULL = DEFAULT_NOTIFICATION_CHANNELS (modules/notifications)
    notification_channels: Mapped[Optional[dict[str, list[str]]]] = mapped_column(JSONB)
    # soft delete: the row stays for payment/referral history, personal data is wiped
    deleted_at: Mapped[Optional[datetime]]

    @validates("email")
    def _sync_email_canonical(self, _key: str, value: Optional[str]) -> Optional[str]:
        self.email_canonical = canonical_email(value) if value else None
        return value
