from typing import Optional

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import GB_TO_BYTES
from app.modules.subscriptions.dto import SubscriptionDto


def traffic_spent_for_good(subscription: SubscriptionDto, used_traffic: int) -> bool:
    """The limit is used up and never comes back: no reset strategy refills it.
    With a periodic reset the panel zeroes the usage next period, so more days
    are still worth something. 0 is no limit."""
    limit = subscription.effective_traffic_limit * GB_TO_BYTES
    return (
        subscription.traffic_limit_strategy is TrafficLimitStrategy.NO_RESET
        and limit > 0
        and used_traffic >= limit
    )


class PanelTrafficUsage:
    """A subscription's used traffic, which only the panel knows."""

    def __init__(self, remnawave_sdk: RemnawaveSDK) -> None:
        self._remnawave_sdk = remnawave_sdk

    async def used_traffic(self, subscription: SubscriptionDto) -> Optional[int]:
        """Bytes, or None when the panel can't be reached. Call it outside a
        transaction: a slow panel mustn't hold a connection."""
        try:
            panel_user = await self._remnawave_sdk.users.get_user_by_id(
                subscription.remnawave_user_id
            )
        except Exception as e:
            logger.warning(
                "Panel usage lookup failed for subscription '{}': {}", subscription.id, e
            )
            return None
        return int(panel_user.used_traffic_bytes)  # the SDK types it as float
