from taskiq import SmartRetryMiddleware
from taskiq_redis import ListRedisScheduleSource

from app.core.exceptions import RemnawavePanelUnavailableError
from app.worker.broker import broker, retry_schedule_source
from app.worker.metrics import TaskMetricsMiddleware


def test_broker_has_a_smart_retry_middleware_scoped_to_panel_unavailability() -> None:
    middleware = next(m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware))
    assert middleware.types_of_exceptions == (RemnawavePanelUnavailableError,)
    assert middleware.schedule_source is retry_schedule_source
    assert middleware.default_retry_label is False


def test_retry_schedule_source_is_a_list_redis_schedule_source() -> None:
    assert isinstance(retry_schedule_source, ListRedisScheduleSource)


def test_first_retry_delay_outlasts_the_panel_breaker_window() -> None:
    # resilient_transport's _RECOVERY_TIMEOUT_S is 30s and the breaker's open
    # window is not refreshed by fail-fast rejections -- a retry landing inside
    # it burns budget while the breaker is still open. Guards that coupling.
    middleware = next(m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware))
    assert middleware.default_delay >= 30.0


def test_broker_has_a_task_metrics_middleware() -> None:
    assert any(isinstance(m, TaskMetricsMiddleware) for m in broker.middlewares)
