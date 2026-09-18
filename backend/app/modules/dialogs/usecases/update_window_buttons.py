from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import DialogWindowKind
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogButtonInputDto, DialogWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.dialogs.validation import validate_buttons
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class UpdateDialogWindowButtonsInput:
    key: str
    buttons: list[DialogButtonInputDto]


class UpdateDialogWindowButtonsUseCase(UseCase[UpdateDialogWindowButtonsInput, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_BUTTONS_UPDATE

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

    async def _execute(
        self, actor: UserDto, data: UpdateDialogWindowButtonsInput
    ) -> DialogWindowDto:
        async with self._uow:
            window = await self._dialog_repository.get_by_key_or_raise(data.key)
            all_windows = await self._dialog_repository.list_all()
            navigable = {w.key for w in all_windows} | {w.key for w in catalog.all_windows()}
            seed_actions = (
                await self._dialog_repository.seed_action_keys(data.key)
                if window.kind == DialogWindowKind.SEED
                else set()
            )

            validate_buttons(
                data.buttons,
                window_key=window.key,
                window_kind=window.kind,
                navigable=navigable,
                seed_actions=seed_actions,
            )

            locales = await self._settings_repository.list_active_locales()
        async with self._uow:
            for button in data.buttons:
                if button.text_key.startswith(catalog.CUSTOM_TEXT_KEY_PREFIX):
                    for locale in locales:
                        await self._translations_repository.seed_missing(
                            locale, button.text_key, "", ""
                        )
            updated = await self._dialog_repository.replace_buttons(data.key, data.buttons)
        await publish_dialog_change(self._redis)
        return updated
