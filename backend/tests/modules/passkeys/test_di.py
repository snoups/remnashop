from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.modules.auth import get_auth_providers
from app.modules.blacklist import get_blacklist_providers
from app.modules.passkeys import get_passkey_providers
from app.modules.passkeys.usecases import ListPasskeysUseCase
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscription_revoker_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers


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
        *get_users_providers(),
        *get_subscription_revoker_providers(),
        *get_auth_providers(),
        *get_settings_providers(),
        *get_blacklist_providers(),
        *get_translations_providers(),
        *get_passkey_providers(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    async with container(scope=Scope.REQUEST) as c:
        assert await c.get(ListPasskeysUseCase) is not None
    await container.close()
