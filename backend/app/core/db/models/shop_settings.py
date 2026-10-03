from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class ShopSettings(BaseSql, TimestampMixin):
    __tablename__ = "shop_settings"

    # Single row, always id=1 -- see modules/settings/repository.py.
    id: Mapped[int] = mapped_column(primary_key=True)

    # NULL = unlimited. No column default here on purpose -- SQLAlchemy's
    # client-side `default=` fires on an explicit None too (it can't tell
    # "unset" from "set to null"), which would make it impossible to ever
    # persist "unlimited" on a first-ever write. ShopSettingsDto's own
    # default (3, matching the hardcoded cap this setting replaced --
    # MAX_ACTIVE_SUBSCRIPTIONS_PER_USER) covers the row-doesn't-exist-yet
    # case instead; every write path sets this column explicitly, so a
    # column-level default is never actually exercised.
    max_active_subscriptions: Mapped[Optional[int]] = mapped_column()

    # Self-service device/link reset cooldowns. Boolean-off means "feature
    # disabled", not "no cooldown" -- checked before the cooldown_hours
    # comparison in every usecase that uses these.
    device_single_reset_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    device_single_reset_cooldown_hours: Mapped[int] = mapped_column(default=0, server_default="0")
    device_all_reset_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    device_all_reset_cooldown_hours: Mapped[int] = mapped_column(default=0, server_default="0")
    link_reset_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    link_reset_cooldown_hours: Mapped[int] = mapped_column(default=0, server_default="0")
