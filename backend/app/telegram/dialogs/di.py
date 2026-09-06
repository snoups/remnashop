from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.dialogs import DialogRepository
from app.modules.translations import TranslationsRepository
from app.telegram.dialogs.config_cache import DialogConfigCache


class DialogConfigProvider(Provider):
    scope = Scope.APP

    @provide
    def get_dialog_config_cache(
        self, session_maker: async_sessionmaker[AsyncSession]
    ) -> DialogConfigCache:
        return DialogConfigCache(session_maker)

    dialog_repository = provide(DialogRepository, scope=Scope.REQUEST)
    translations_repository = provide(TranslationsRepository, scope=Scope.REQUEST)
