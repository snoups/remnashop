from datetime import datetime, timedelta
from typing import Final

from app.modules.subscriptions import LiveSubscriptionDto

_EXPIRING_DAYS: Final[int] = 30


def expiring_window(live: list[LiveSubscriptionDto], now: datetime) -> list[LiveSubscriptionDto]:
    horizon = now + timedelta(days=_EXPIRING_DAYS)
    return [row for row in live if now <= row.expire_at < horizon]
