from typing import Final

from taskiq import SmartRetryMiddleware
from taskiq.serializers import ORJSONSerializer
from taskiq_redis import ListQueueBroker, ListRedisScheduleSource

from app.core.config import AppConfig
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.json import json_default
from app.worker.metrics import TaskMetricsMiddleware

broker = ListQueueBroker(url=AppConfig.get().redis.dsn).with_serializer(
    ORJSONSerializer(default=json_default)
)
# Module-level singleton (constructed at import time) -- its Redis connection
# binds to whichever asyncio event loop first touches it. pytest-asyncio gives
# each test its own loop, so calling a real `.kiq()` in more than one test
# across a full-suite run breaks with a cross-loop RuntimeError (fine in
# isolation, since only one loop ever exists then). Every test that needs to
# assert a real dispatch happened should monkeypatch the specific task's
# `.kiq()` instead of calling through to this broker -- see
# tests/modules/payments/test_webhook_router.py's `_fake_kiq` pattern for the
# shape. Production is unaffected: one process, one loop, for the worker's
# whole lifetime.

# Used by SmartRetryMiddleware below (in this process, to schedule a delayed
# retry) and by scheduler.py (in the scheduler process, to actually poll and
# dispatch it at the right time) -- same Redis keys, two processes.
RETRY_SCHEDULE_PREFIX: Final[str] = "taskiq_retry_schedule"

retry_schedule_source = ListRedisScheduleSource(
    url=AppConfig.get().redis.dsn, prefix=RETRY_SCHEDULE_PREFIX
)

# Must outlast resilient_transport's _RECOVERY_TIMEOUT_S (30s): the breaker's
# open window is a fixed 30s from the trip and is NOT refreshed by fail-fast
# rejections, so a retry landing inside it just burns budget while the breaker
# is still open -- the exact failure this policy exists to prevent. taskiq's
# make_delay is linear (delay * retries, capped at max_delay_exponent) despite
# the "exponent" name; at 45s the retries land ~45s and ~105s after the first
# failure, both clear of the window even with the scheduler's 60s poll.
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
        # Intentionally ONLY the fail-fast breaker-open case -- that error is
        # raised before the request leaves the process, so a retry is provably
        # safe. Real transport errors (httpx.HTTPError, remnapy ServerError)
        # stay non-retryable: a POST/PATCH that landed but lost its response
        # would double-apply -- orphan panel users from
        # PurchaseSubscriptionUseCase._purchase_new, and the keyless (promocode/
        # referral) relative extend_user in _renew. Widening this needs those
        # paths made idempotent first.
        types_of_exceptions=(RemnawavePanelUnavailableError,),
    ),
    TaskMetricsMiddleware(),
)
