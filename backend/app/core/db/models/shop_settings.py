from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class ShopSettings(BaseSql, TimestampMixin):
    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # NULL = unlimited. No column default: SQLAlchemy's `default=` also fires
    # on an explicit None, so "unlimited" could never be the first value
    # written. ShopSettingsDto's default covers a missing row.
    max_active_subscriptions: Mapped[Optional[int]] = mapped_column()

    # Self-service device/link reset cooldowns. Off means "feature disabled",
    # not "no cooldown"; usecases check it before cooldown_hours.
    device_single_reset_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    device_single_reset_cooldown_hours: Mapped[int] = mapped_column(default=0, server_default="0")
    device_all_reset_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    device_all_reset_cooldown_hours: Mapped[int] = mapped_column(default=0, server_default="0")
    link_reset_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    link_reset_cooldown_hours: Mapped[int] = mapped_column(default=0, server_default="0")
    referral_reset_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    referral_reset_cooldown_hours: Mapped[int] = mapped_column(default=0, server_default="0")

    # Where a customer reaches support, both optional: a Telegram username (without
    # "@", maybe with "?direct") and a page opened in the browser. The cabinet offers
    # whichever is set.
    support_telegram: Mapped[Optional[str]] = mapped_column(String(40))
    support_url: Mapped[Optional[str]] = mapped_column(String(512))

    # sent to every gateway instead of the customer's own email; set, nobody is asked for one
    payment_email: Mapped[Optional[str]] = mapped_column(String(320))
