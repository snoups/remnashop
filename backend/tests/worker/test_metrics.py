from taskiq.message import TaskiqMessage
from taskiq.result import TaskiqResult

import app.modules.event_log.tasks  # noqa: F401 - registers the Gauge whatever the collection order
from app.core.metrics import WORKER_METRICS_REGISTRY, TaskMetricsMiddleware
from app.worker.metrics import (
    _sample_queue_depth,
    _sample_scheduled_retries,
)


def test_worker_metrics_registry_serves_the_outbox_gauges() -> None:
    # event_log.tasks registers its two gauges onto this shared registry --
    # confirms the relocation didn't leave them on a registry nothing serves.
    names = {
        sample.name for metric in WORKER_METRICS_REGISTRY.collect() for sample in metric.samples
    }
    assert "remnashop_event_outbox_unprocessed" in names
    assert "remnashop_event_outbox_oldest_unprocessed_age_seconds" in names


async def test_sample_queue_depth_reads_the_redis_list_length(redis) -> None:
    queue_name = "remnashop-test-queue-depth"
    await redis.delete(queue_name)
    await redis.lpush(queue_name, "a", "b", "c")

    await _sample_queue_depth(redis, queue_name)

    assert WORKER_METRICS_REGISTRY.get_sample_value("remnashop_taskiq_queue_depth") == 3.0

    await redis.delete(queue_name)


async def test_sample_scheduled_retries_counts_pending_retry_data_keys(redis) -> None:
    prefix = "remnashop-test-retry-schedule"
    await redis.delete(f"{prefix}:data:a", f"{prefix}:data:b")
    await redis.set(f"{prefix}:data:a", "x")
    await redis.set(f"{prefix}:data:b", "y")

    await _sample_scheduled_retries(redis, prefix)

    assert WORKER_METRICS_REGISTRY.get_sample_value("remnashop_taskiq_scheduled_retries") == 2.0

    await redis.delete(f"{prefix}:data:a", f"{prefix}:data:b")


def _make_message(task_name: str) -> TaskiqMessage:
    return TaskiqMessage(task_id="test-task-id", task_name=task_name, labels={}, args=[], kwargs={})


def _make_result(*, is_err: bool, execution_time: float) -> TaskiqResult:
    return TaskiqResult(is_err=is_err, return_value=None, execution_time=execution_time)


async def test_task_metrics_middleware_records_a_successful_run() -> None:
    middleware = TaskMetricsMiddleware()

    await middleware.post_execute(
        _make_message("app.modules.event_log.tasks:sweep_outbox_task"),
        _make_result(is_err=False, execution_time=0.42),
    )

    total_time = WORKER_METRICS_REGISTRY.get_sample_value(
        "remnashop_taskiq_task_duration_seconds_sum",
        {"task_name": "app.modules.event_log.tasks:sweep_outbox_task", "outcome": "success"},
    )
    assert total_time is not None and total_time >= 0.42


async def test_task_metrics_middleware_records_a_failed_run_under_its_own_outcome() -> None:
    middleware = TaskMetricsMiddleware()

    await middleware.post_execute(
        _make_message("app.modules.transactions.tasks:reconcile_paid_transactions_task"),
        _make_result(is_err=True, execution_time=0.1),
    )

    error_count = WORKER_METRICS_REGISTRY.get_sample_value(
        "remnashop_taskiq_task_duration_seconds_count",
        {
            "task_name": "app.modules.transactions.tasks:reconcile_paid_transactions_task",
            "outcome": "error",
        },
    )
    assert error_count is not None and error_count >= 1
