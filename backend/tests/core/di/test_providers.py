import pytest
from sqlalchemy.exc import OperationalError

from app.core.config import AppConfig
from app.core.di.providers import DatabaseProvider, RemnawaveProvider, get_core_providers


def test_remnawave_provider_is_registered() -> None:
    providers = get_core_providers()
    assert any(isinstance(p, RemnawaveProvider) for p in providers)


async def test_get_engine_fails_fast_on_unreachable_database() -> None:
    config = AppConfig.get()
    # Port 1 is never a real Postgres -- connection is refused immediately,
    # exercising the fail-fast path without waiting on a real timeout.
    config.database.host = "127.0.0.1"
    config.database.port = 1

    provider = DatabaseProvider()
    with pytest.raises(OperationalError):
        async for _ in provider.get_engine(config):
            pass
