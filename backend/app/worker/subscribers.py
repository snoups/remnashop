from loguru import logger

from app.core.event_bus import EventBus
from app.modules.advertising.subscribers import (
    register_subscribers as register_advertising_subscribers,
)
from app.modules.auth.subscribers import register_subscribers as register_auth_subscribers
from app.modules.loyalty.subscribers import register_subscribers as register_loyalty_subscribers
from app.modules.notifications.subscribers import (
    register_subscribers as register_notification_subscribers,
)
from app.modules.oauth.subscribers import register_subscribers as register_oauth_subscribers
from app.modules.referrals.subscribers import register_subscribers as register_referral_subscribers


def register_all_subscribers(bus: EventBus) -> None:
    # only the worker dispatches stored events (outbox sweep), so only it registers
    register_auth_subscribers(bus)
    register_oauth_subscribers(bus)
    register_referral_subscribers(bus)
    register_advertising_subscribers(bus)
    register_loyalty_subscribers(bus)
    register_notification_subscribers(bus)
    logger.debug(f"Event bus ready: {bus.handler_count} handler(s) registered")
