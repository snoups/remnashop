from typing import Final

from prometheus_client import Counter

from app.core.metrics import WORKER_METRICS_REGISTRY

BROADCAST_EMAILS: Final[Counter] = Counter(
    "remnashop_broadcast_emails_total",
    "Broadcast emails by result",
    labelnames=("result",),
    registry=WORKER_METRICS_REGISTRY,
)
