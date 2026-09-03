from prometheus_client import CollectorRegistry, Gauge
from sqlalchemy.ext.asyncio import AsyncEngine


def register_db_pool_metrics(engine: AsyncEngine, *, registry: CollectorRegistry) -> None:
    # engine.pool is typed as the base Pool class, which doesn't declare
    # size()/checkedout() -- both exist on the AsyncAdaptedQueuePool SQLAlchemy
    # actually constructs at runtime for an async engine.
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
