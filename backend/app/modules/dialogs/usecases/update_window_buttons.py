from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import DialogWindowKind, Locale
from app.core.ports import BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import (
    DialogWindowDto,
    UpdateDialogWindowButtonsDto,
)
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.validation import validate_buttons
from app.modules.translations import (
    TranslationRepository,
    assert_fluent_compiles,
    serialize_to_fluent,
)

# Telegram rejects a button with no text, so a new one never starts empty.
_NEW_BUTTON_LABELS: Final[dict[Locale, str]] = {Locale.RU: "Кнопка"}
_NEW_BUTTON_LABEL_DEFAULT: Final[str] = "Button"


class UpdateDialogWindowButtonsUseCase(UseCase[UpdateDialogWindowButtonsDto, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_BUTTONS_UPDATE

    def __init__(
        self,
        dialog_repository: DialogRepository,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
        bot_signals: BotSignals,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._translation_repository = translation_repository
        self._uow = uow
        self._bot_signals = bot_signals

    async def _execute(self, actor: Actor, data: UpdateDialogWindowButtonsDto) -> DialogWindowDto:
        async with self._uow:
            window = await self._dialog_repository.get_by_key_or_raise(data.key)
            all_windows = await self._dialog_repository.list_all()
            navigable = {w.key for w in all_windows} | {w.key for w in catalog.all_windows()}
            seed_actions = (
                await self._dialog_repository.seed_action_keys(data.key)
                if window.kind == DialogWindowKind.SEED
                else set()
            )

            system_text_keys = await self._dialog_repository.system_text_keys(data.key)

            validate_buttons(
                data.buttons,
                window_key=window.key,
                window_kind=window.kind,
                navigable=navigable,
                seed_actions=seed_actions,
                system_text_keys=system_text_keys,
            )

            locales = await self._translation_repository.list_active_locales()
        async with self._uow:
            seeded = False
            for button in data.buttons:
                if button.text_key.startswith(catalog.CUSTOM_TEXT_KEY_PREFIX):
                    seeded = True
                    for locale in locales:
                        label = _NEW_BUTTON_LABELS.get(locale, _NEW_BUTTON_LABEL_DEFAULT)
                        await self._translation_repository.seed_missing(
                            locale, button.text_key, "", label
                        )
            if seeded:
                await self._check_locales_compile(locales)
            updated = await self._dialog_repository.replace_buttons(data.key, data.buttons)
        await self._bot_signals.dialogs_changed()
        return updated

    async def _check_locales_compile(self, locales: list[Locale]) -> None:
        for locale in locales:
            entries = await self._translation_repository.list_by_locale(locale)
            assert_fluent_compiles(locale, serialize_to_fluent(entries))
