from typing import Final

from taskiq import SmartRetryMiddleware
from taskiq.serializers import ORJSONSerializer
from taskiq_redis import ListQueueBroker, ListRedisScheduleSource

from app.core.config import AppConfig
from app.core.exceptions import RemnawavePanelUnavailableError, RetryableTaskError
from app.core.json import json_default
from app.core.metrics import TaskMetricsMiddleware

broker = ListQueueBroker(url=AppConfig.get().redis.dsn).with_serializer(
    ORJSONSerializer(default=json_default)
)
# Built at import time; its Redis connection binds to the first event loop that
# uses it. pytest-asyncio gives each test its own loop, so tests monkeypatch a
# task's `.kiq()` (tests/core/test_event_bus.py's `_capture_kiq`) instead of
# going through the broker.

# Shared Redis keys: SmartRetryMiddleware below schedules a delayed retry,
# scheduler.py dispatches it when due.
RETRY_SCHEDULE_PREFIX: Final[str] = "taskiq_retry_schedule"

retry_schedule_source = ListRedisScheduleSource(
    url=AppConfig.get().redis.dsn, prefix=RETRY_SCHEDULE_PREFIX
)

# Longer than resilient_transport's _RECOVERY_TIMEOUT_S (30s, counted from the
# trip), or a retry would hit the still-open breaker and waste an attempt.
# taskiq's make_delay is linear despite the "exponent" name: retries land at
# ~45s and ~105s, clear of the window even with the scheduler's 60s poll.
_RETRY_FIRST_DELAY_S: Final[float] = 45.0

broker.add_middlewares(
    SmartRetryMiddleware(
        # Total attempts, not retries: taskiq guards with retries <
        # default_retry_count, so 3 -> original run + 2 retries. Kept in sync
        # with each task's max_retries in modules/subscriptions/tasks.py.
        default_retry_count=3,
        default_retry_label=False,  # opt-in per task via retry_on_error=True
        default_delay=_RETRY_FIRST_DELAY_S,
        use_delay_exponent=True,
        use_jitter=True,
        max_delay_exponent=60.0,
        schedule_source=retry_schedule_source,
        # Only the breaker-open error: it's raised before the request leaves,
        # so a retry is safe. A real transport error may hide a POST/PATCH that
        # landed, and retrying it would orphan panel users in NewPurchase and
        # double the keyless extend_user in RenewPurchase.
        # RetryableTaskError: raised by a task only when a repeat is safe (nothing done yet,
        # or a pinned, keyed write that a repeat re-applies as is)
        types_of_exceptions=(RemnawavePanelUnavailableError, RetryableTaskError),
    ),
    TaskMetricsMiddleware(),
)
