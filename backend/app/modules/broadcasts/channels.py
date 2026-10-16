from app.core.enums import BroadcastDelivery


def sends_telegram(delivery: BroadcastDelivery) -> bool:
    return delivery is not BroadcastDelivery.EMAIL


def sends_email(delivery: BroadcastDelivery, email_fallback: bool) -> bool:
    return delivery is not BroadcastDelivery.TELEGRAM or email_fallback
