from prometheus_client import CollectorRegistry
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import AppConfig
from app.core.metrics import register_db_pool_metrics


async def test_register_db_pool_metrics_reflects_live_pool_state(config: AppConfig) -> None:
    engine = create_async_engine(config.database.dsn, pool_size=3, max_overflow=2)
    registry = CollectorRegistry()

    register_db_pool_metrics(engine, registry=registry)

    assert registry.get_sample_value("remnashop_db_pool_size") == 3.0
    assert registry.get_sample_value("remnashop_db_pool_checked_out") == 0.0

    await engine.dispose()
