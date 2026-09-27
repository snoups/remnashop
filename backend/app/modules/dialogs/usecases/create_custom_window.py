from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from redis.asyncio import Redis

from app.core.constants import DEFAULT_BANNER_NAME
from app.core.db.uow import UnitOfWork
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
    name: str
    # Every window starts on the shared banner; the inspector is where an
    # admin moves it to its own or turns it off.
    banner_name: Optional[str] = DEFAULT_BANNER_NAME


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
                await self._translations_repository.seed_missing(locale, text_key, "", data.name)
            window = await self._dialog_repository.create_custom_window(
                key, CreateCustomWindowDto(banner_name=data.banner_name, name=data.name)
            )
        await publish_dialog_change(self._redis)
        return window
