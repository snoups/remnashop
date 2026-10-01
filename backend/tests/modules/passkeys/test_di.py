from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.passkeys.usecases import ListPasskeysUseCase
from app.modules.providers import get_module_providers


class _BoundSession(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


async def test_passkey_providers_resolve_list_use_case(
    config: AppConfig, session: AsyncSession
) -> None:
    container = make_async_container(
        *get_core_providers(),
        *get_module_providers(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    async with container(scope=Scope.REQUEST) as c:
        assert await c.get(ListPasskeysUseCase) is not None
    await container.close()
