from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import ActiveLocalesDto
from app.modules.translations.repository import TranslationRepository


class ListActiveLocalesUseCase(UseCase[None, ActiveLocalesDto]):
    required_permission = Permission.LOCALES_VIEW

    def __init__(self, translation_repository: TranslationRepository, uow: UnitOfWork) -> None:
        self._translation_repository = translation_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> ActiveLocalesDto:
        async with self._uow:
            return await self._translation_repository.get_locales()
