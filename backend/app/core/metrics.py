from typing import Any, Final

from prometheus_client import CollectorRegistry, Gauge, Histogram
from sqlalchemy.ext.asyncio import AsyncEngine
from taskiq import TaskiqMiddleware
from taskiq.message import TaskiqMessage
from taskiq.result import TaskiqResult

# lives here so module code that runs only in the worker can register on it
WORKER_METRICS_REGISTRY: Final[CollectorRegistry] = CollectorRegistry()


def register_db_pool_metrics(engine: AsyncEngine, *, registry: CollectorRegistry) -> None:
    # engine.pool is typed as the base Pool, which lacks size()/checkedout();
    # the AsyncAdaptedQueuePool an async engine actually gets has both
    Gauge(
        "remnashop_db_pool_size",
        "Configured SQLAlchemy connection pool size",
        registry=registry,
    ).set_function(engine.pool.size)  # type: ignore[attr-defined]
    Gauge(
        "remnashop_db_pool_checked_out",
        "SQLAlchemy connections currently checked out",
        registry=registry,
    ).set_function(engine.pool.checkedout)  # type: ignore[attr-defined]


TASK_DURATION: Final[Histogram] = Histogram(
    "remnashop_taskiq_task_duration_seconds",
    "Taskiq task execution time by task and outcome",
    labelnames=("task_name", "outcome"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=WORKER_METRICS_REGISTRY,
)


class TaskMetricsMiddleware(TaskiqMiddleware):
    async def post_execute(self, message: TaskiqMessage, result: TaskiqResult[Any]) -> None:
        outcome = "error" if result.is_err else "success"
        TASK_DURATION.labels(task_name=message.task_name, outcome=outcome).observe(
            result.execution_time
        )
