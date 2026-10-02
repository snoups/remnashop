from uuid import uuid4

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.dto import (
    CreateCustomDialogWindowDto,
    CreateCustomWindowDto,
    DialogWindowDto,
)
from app.modules.dialogs.repository import DialogRepository
from app.modules.translations import TranslationRepository


class CreateCustomDialogWindowUseCase(UseCase[CreateCustomDialogWindowDto, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_CREATE

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

    async def _execute(self, actor: Actor, data: CreateCustomDialogWindowDto) -> DialogWindowDto:
        async with self._uow:
            key = f"custom-{uuid4().hex}"
            text_key = f"msg-dialog-{key}"
            locales = await self._translation_repository.list_active_locales()
        async with self._uow:
            for locale in locales:
                await self._translation_repository.seed_missing(locale, text_key, "", data.name)
            window = await self._dialog_repository.create_custom_window(
                key, CreateCustomWindowDto(banner_name=data.banner_name, name=data.name)
            )
        await self._bot_signals.dialogs_changed()
        return window
