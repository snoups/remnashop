from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.dialogs import get_dialogs_providers
from app.modules.dialogs.usecases import ListDialogWindowsUseCase, UpdateDialogWindowButtonsUseCase
from app.modules.settings import get_settings_providers
from app.modules.translations import get_translations_providers


class _BoundSession(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


async def test_usecases_resolve(config: AppConfig, session: AsyncSession) -> None:
    container = make_async_container(
        *get_core_providers(),
        *get_settings_providers(),
        *get_translations_providers(),
        *get_dialogs_providers(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    async with container(scope=Scope.REQUEST) as c:
        assert await c.get(ListDialogWindowsUseCase) is not None
        assert await c.get(UpdateDialogWindowButtonsUseCase) is not None
    await container.close()
