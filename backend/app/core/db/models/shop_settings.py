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
