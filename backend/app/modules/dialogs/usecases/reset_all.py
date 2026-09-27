from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners import BannerRepository
from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._banners import drop_window_banners
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository, split_message_key
from app.modules.users import UserDto


class ResetAllDialogsUseCase(UseCase[None, None]):
    required_permission = Permission.DIALOGS_WINDOWS_RESET_ALL

    def __init__(
        self,
        dialog_repository: DialogRepository,
        translations_repository: TranslationsRepository,
        settings_repository: SettingsRepository,
        banner_repository: BannerRepository,
        config: AppConfig,
        uow: UnitOfWork,
        redis: Redis,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._banner_repository = banner_repository
        self._config = config
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self._uow:
            locales = await self._settings_repository.list_active_locales()
            text_keys: set[str] = set()
            for window in catalog.all_windows():
                text_keys.update(window.text_keys)
                text_keys.update(b.text_key for b in window.buttons)
        async with self._uow:
            # "Everything back to how it shipped" includes windows that were not
            # shipped at all: a custom one has no default to fall back to.
            for key in await self._dialog_repository.list_custom_keys():
                await self._dialog_repository.delete_custom_window(key)
                await drop_window_banners(self._banner_repository, self._config, key)
            for key in await self._dialog_repository.list_seed_keys():
                await self._dialog_repository.reset_to_snapshot(key)
            for locale in locales:
                for text_key in text_keys:
                    message_id, attribute_id = split_message_key(text_key)
                    try:
                        await self._translations_repository.reset_value(
                            locale, message_id, attribute_id
                        )
                    except NotFoundError:
                        continue
        await publish_dialog_change(self._redis)
