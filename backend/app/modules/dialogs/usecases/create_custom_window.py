from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import BannerName
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.dto import CreateCustomWindowDto, DialogWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class CreateCustomDialogWindowInput:
    title_text: str
    banner_name: Optional[BannerName] = None


class CreateCustomDialogWindowUseCase(UseCase[CreateCustomDialogWindowInput, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_CREATE

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
        self, actor: UserDto, data: CreateCustomDialogWindowInput
    ) -> DialogWindowDto:
        async with self._uow:
            key = f"custom-{uuid4().hex}"
            text_key = f"msg-dialog-{key}"
            locales = await self._settings_repository.list_active_locales()
        async with self._uow:
            for locale in locales:
                await self._translations_repository.seed_missing(
                    locale, text_key, "", data.title_text
                )
            window = await self._dialog_repository.create_custom_window(
                key, CreateCustomWindowDto(banner_name=data.banner_name)
            )
        await publish_dialog_change(self._redis)
        return window
