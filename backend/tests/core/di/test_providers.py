import pytest
from redis.asyncio import Redis
from sqlalchemy.exc import OperationalError

from app.core.config import AppConfig
from app.core.di.providers import DatabaseProvider, RemnawaveProvider, get_core_providers
from app.core.panel_writes import PanelWriteRecorder
from app.core.resilient_transport import ResilientTransport


def test_remnawave_provider_is_registered() -> None:
    providers = get_core_providers()
    assert any(isinstance(p, RemnawaveProvider) for p in providers)


async def test_remnawave_client_transport_is_wrapped(config: AppConfig, redis: Redis) -> None:
    provider = RemnawaveProvider()
    async for sdk in provider.get_remnawave(config, redis):
        transport = sdk._client._transport
        assert isinstance(transport, PanelWriteRecorder)
        assert isinstance(transport._wrapped, ResilientTransport)
        break


async def test_get_engine_fails_fast_on_unreachable_database() -> None:
    config = AppConfig.get()
    # nothing listens on port 1, so the connection is refused at once
    config.database.host = "127.0.0.1"
    config.database.port = 1

    provider = DatabaseProvider()
    with pytest.raises(OperationalError):
        async for _ in provider.get_engine(config):
            pass
