from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.providers import get_module_providers
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.di import DialogConfigProvider


class _BoundSession(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


async def test_dialog_config_cache_resolves(config: AppConfig, session: AsyncSession) -> None:
    container = make_async_container(
        *get_core_providers(),
        *get_module_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    cache = await container.get(DialogConfigCache)
    assert cache is not None
    await container.close()
