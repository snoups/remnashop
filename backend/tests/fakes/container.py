from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.providers import get_module_providers


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


def make_test_container(
    session: AsyncSession, config: AppConfig, *providers: Provider
) -> AsyncContainer:
    # the last provider of a type wins: the test session replaces the real
    # AsyncSession factory, so every request shares the rolled-back transaction
    return make_async_container(
        *get_core_providers(),
        *get_module_providers(),
        *providers,
        _TestSessionProvider(session),
        context={AppConfig: config},
    )
