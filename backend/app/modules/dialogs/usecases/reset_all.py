from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository
from app.modules.users import UserDto


class ResetAllDialogsUseCase(UseCase[None, None]):
    required_permission = Permission.DIALOGS_WINDOWS_RESET_ALL

    def __init__(
        self,
        dialog_repository: DialogRepository,
        translations_repository: TranslationsRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        redis: Redis,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: UserDto, data: None) -> None:
        locales = await self._settings_repository.list_active_locales()
        text_keys: set[str] = set()
        for window in catalog.all_windows():
            text_keys.update(window.text_keys)
            text_keys.update(b.text_key for b in window.buttons)
        async with self._uow:
            for key in await self._dialog_repository.list_seed_keys():
                await self._dialog_repository.reset_to_snapshot(key)
            for locale in locales:
                for message_id in text_keys:
                    try:
                        await self._translations_repository.reset_value(locale, message_id, "")
                    except NotFoundError:
                        continue
        await publish_dialog_change(self._redis)
