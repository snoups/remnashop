from typing import Final

from prometheus_client import Counter

from app.core.metrics import WORKER_METRICS_REGISTRY

CUSTOMER_NOTIFICATIONS: Final[Counter] = Counter(
    "remnashop_customer_notifications_total",
    "Customer notifications by channel and outcome",
    labelnames=("channel", "result"),
    registry=WORKER_METRICS_REGISTRY,
)
