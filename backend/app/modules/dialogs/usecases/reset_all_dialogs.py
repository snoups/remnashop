from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.ports import BotSignals, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners import BannerRepository
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogWindowDto
from app.modules.dialogs.events import DialogChangedEvent
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._banners import drop_window_banners
from app.modules.translations import TranslationRepository, split_message_key


class ResetAllDialogsUseCase(UseCase[None, list[DialogWindowDto]]):
    required_permission = Permission.DIALOGS_WINDOWS_RESET_ALL

    def __init__(
        self,
        dialog_repository: DialogRepository,
        translation_repository: TranslationRepository,
        banner_repository: BannerRepository,
        config: AppConfig,
        uow: UnitOfWork,
        bot_signals: BotSignals,
        event_publisher: EventPublisher,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._translation_repository = translation_repository
        self._banner_repository = banner_repository
        self._config = config
        self._uow = uow
        self._bot_signals = bot_signals
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> list[DialogWindowDto]:
        async with self._uow:
            locales = await self._translation_repository.list_active_locales()
            text_keys: set[str] = set()
            for window in catalog.all_windows():
                text_keys.update(window.text_keys)
                text_keys.update(b.text_key for b in window.buttons)

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
                        await self._translation_repository.reset_value(
                            locale, message_id, attribute_id
                        )
                    except NotFoundError:
                        continue
            await self._event_publisher.publish(DialogChangedEvent(actor=actor, action="reset_all"))
            windows = await self._dialog_repository.list_all()
        await self._bot_signals.dialogs_changed()
        return windows
