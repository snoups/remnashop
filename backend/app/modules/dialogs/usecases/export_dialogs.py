from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import (
    DialogButtonInputDto,
    DialogExportDto,
    DialogTextExportDto,
    DialogWindowDto,
    DialogWindowExportDto,
)
from app.modules.dialogs.repository import DialogRepository
from app.modules.translations import TranslationRepository, join_message_key

# Bumped when the payload's meaning changes: banner_name went from a fixed
# category to a free name, and a button's icon moved out into translations.
# An older file would import cleanly and land wrong, so it is refused instead.
EXPORT_VERSION: Final[int] = 2


def dialog_text_keys(windows: list[DialogWindowDto]) -> set[str]:
    keys: set[str] = set()
    for window in windows:
        keys.update(catalog.window_text_keys(window.key))
        keys.update(button.text_key for button in window.buttons)
    return keys


class ExportDialogsUseCase(UseCase[None, DialogExportDto]):
    required_permission = Permission.DIALOGS_EXPORT

    def __init__(
        self,
        dialog_repository: DialogRepository,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._translation_repository = translation_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> DialogExportDto:
        async with self._uow:
            windows = await self._dialog_repository.list_all()
            locales = await self._translation_repository.list_active_locales()
            text_keys = dialog_text_keys(windows)

            texts: list[DialogTextExportDto] = []
            for locale in locales:
                for entry in await self._translation_repository.list_by_locale(locale):
                    if join_message_key(entry.message_id, entry.attribute_id) not in text_keys:
                        continue
                    texts.append(
                        DialogTextExportDto(
                            locale=locale,
                            message_id=entry.message_id,
                            attribute_id=entry.attribute_id,
                            value=entry.value,
                        )
                    )

            return DialogExportDto(
                version=EXPORT_VERSION,
                windows=[_to_export(window) for window in windows],
                texts=texts,
            )


def _to_export(window: DialogWindowDto) -> DialogWindowExportDto:
    return DialogWindowExportDto(
        key=window.key,
        kind=window.kind,
        banner_name=window.banner_name,
        name=window.name,
        is_enabled=window.is_enabled,
        position=window.position,
        buttons=[
            DialogButtonInputDto(
                row=button.row,
                column=button.column,
                text_key=button.text_key,
                link_type=button.link_type,
                style=button.style,
                visibility_condition=button.visibility_condition,
                action_key=button.action_key,
                target_window_key=button.target_window_key,
                url_value=button.url_value,
                is_hidden=button.is_hidden,
            )
            for button in window.buttons
        ],
    )
