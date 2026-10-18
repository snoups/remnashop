from taskiq import SmartRetryMiddleware
from taskiq_redis import ListRedisScheduleSource

from app.core.broker import broker, retry_schedule_source
from app.core.exceptions import RemnawavePanelUnavailableError, RetryableTaskError
from app.core.metrics import TaskMetricsMiddleware


def test_broker_has_a_smart_retry_middleware_scoped_to_safe_retries() -> None:
    middleware = next(m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware))
    assert middleware.types_of_exceptions == (RemnawavePanelUnavailableError, RetryableTaskError)
    assert middleware.schedule_source is retry_schedule_source
    assert middleware.default_retry_label is False


def test_retry_schedule_source_is_a_list_redis_schedule_source() -> None:
    assert isinstance(retry_schedule_source, ListRedisScheduleSource)


def test_first_retry_delay_outlasts_the_panel_breaker_window() -> None:
    # a retry inside resilient_transport's 30s breaker window would be wasted
    middleware = next(m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware))
    assert middleware.default_delay >= 30.0


def test_broker_has_a_task_metrics_middleware() -> None:
    assert any(isinstance(m, TaskMetricsMiddleware) for m in broker.middlewares)


def test_broker_has_no_read_timeout_for_its_blocking_brpop() -> None:
    # an idle BRPOP would time out and stop the worker's listen loop
    kwargs = broker.connection_pool.connection_kwargs
    assert kwargs.get("socket_timeout") is None
    assert kwargs["socket_connect_timeout"] == 5
    assert kwargs["health_check_interval"] == 30
