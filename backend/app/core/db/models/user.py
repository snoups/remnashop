from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Locale, Role


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
        # Mirrors LOGIN_PATTERN (app/core/constants.py) — Latin letters, digits, dots,
        # underscores, hyphens only. The API-level check alone doesn't cover rows
        # written any other way, so this is the actual guarantee.
        CheckConstraint(
            "login IS NULL OR login ~ '^[A-Za-z0-9._-]+$'",
            name="ck_users_login_charset",
        ),
        CheckConstraint(
            "personal_discount BETWEEN 0 AND 100", name="ck_users_personal_discount_range"
        ),
        CheckConstraint(
            "purchase_discount BETWEEN 0 AND 100", name="ck_users_purchase_discount_range"
        ),
        CheckConstraint("points >= 0", name="ck_users_points_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(32), index=True)

    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, unique=True)
    login: Mapped[Optional[str]] = mapped_column(String(64), index=True, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(161))

    name: Mapped[str] = mapped_column(String())
    role: Mapped[Role] = mapped_column(index=True)
    language: Mapped[Locale]

    is_blocked: Mapped[bool]

    permission_grants: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    permission_revokes: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    ip_allowlist: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    personal_discount: Mapped[int] = mapped_column(default=0, server_default="0")
    purchase_discount: Mapped[int] = mapped_column(default=0, server_default="0")
    # the promocode that set each discount; NULL when an admin set it or it's 0
    personal_discount_promocode_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("promocodes.id", ondelete="SET NULL")
    )
    purchase_discount_promocode_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("promocodes.id", ondelete="SET NULL")
    )
    # Nullable: generated on every new create(), pre-existing rows may lack
    # one (see the plan's Global Constraints) -- multiple NULLs are fine
    # under a UNIQUE index.
    referral_code: Mapped[Optional[str]] = mapped_column(String(16), unique=True, index=True)
    points: Mapped[Decimal] = mapped_column(Numeric(12, 0), default=Decimal(0), server_default="0")
    # One-way latch: True until the user's first trial activation, then
    # never re-derived from subscription history (a trial subscription can
    # later become DELETED via a trial->paid conversion -- see
    # NewPurchase._upgrade_trial_in_place -- so "has a trial row"
    # would give the wrong answer post-conversion).
    is_trial_available: Mapped[bool] = mapped_column(default=True, server_default="true")
    # dashboard bell: events up to this moment count as read
    notifications_seen_at: Mapped[Optional[datetime]]
    # NULL = the default (critical) groups; see NOTIFICATION_GROUPS
    notification_groups: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    # soft delete: the row stays for payment/referral history, personal data is wiped
    deleted_at: Mapped[Optional[datetime]]
