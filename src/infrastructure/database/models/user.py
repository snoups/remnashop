from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.enums import Locale, Role

from .base import BaseSql
from .timestamp import TimestampMixin


class User(BaseSql, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)

    login: Mapped[Optional[str]] = mapped_column(String(64), index=True, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(512))
    is_email_verified: Mapped[bool] = mapped_column(default=False)
    pending_email: Mapped[Optional[str]] = mapped_column(String(255))
    email_verification_code_hash: Mapped[Optional[str]] = mapped_column(String(128))
    email_verification_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    username: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    referral_code: Mapped[str] = mapped_column(String(64), index=True, unique=True)

    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[Role] = mapped_column(index=True)
    language: Mapped[Locale]

    personal_discount: Mapped[int]
    purchase_discount: Mapped[int]
    points: Mapped[int]

    is_blocked: Mapped[bool]
    is_bot_blocked: Mapped[bool]
    is_rules_accepted: Mapped[bool]
    is_trial_available: Mapped[bool]

    current_subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "subscriptions.id",
            ondelete="SET NULL",
        )
    )
