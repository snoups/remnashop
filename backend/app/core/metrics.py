from typing import Final

from prometheus_client import CollectorRegistry, Gauge
from sqlalchemy.ext.asyncio import AsyncEngine

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
