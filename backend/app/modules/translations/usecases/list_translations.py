from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.repository import TranslationsRepository
from app.modules.users import UserDto


class ListTranslationsUseCase(UseCase[None, list[TranslationEntryDto]]):
    required_permission = Permission.TRANSLATIONS_VIEW

    def __init__(self, translations_repository: TranslationsRepository, uow: UnitOfWork) -> None:
        self._translations_repository = translations_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> list[TranslationEntryDto]:
        async with self._uow:
            return await self._translations_repository.list_all()
