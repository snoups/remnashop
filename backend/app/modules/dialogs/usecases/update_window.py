from dataclasses import dataclass
from typing import Optional

from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import DialogWindowKind
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.dto import DialogWindowDto, UpdateDialogWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.dialogs.usecases._window_texts import validate_stored_window_texts
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository


@dataclass(frozen=True, kw_only=True)
class UpdateDialogWindowInput:
    key: str
    banner_name: Optional[str] = None
    banner_name_provided: bool = False
    is_enabled: Optional[bool] = None
    name: Optional[str] = None


class UpdateDialogWindowUseCase(UseCase[UpdateDialogWindowInput, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_UPDATE

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

    async def _execute(self, actor: Actor, data: UpdateDialogWindowInput) -> DialogWindowDto:
        async with self._uow:
            if data.is_enabled is False:
                current = await self._dialog_repository.get_by_key_or_raise(data.key)
                if current.kind == DialogWindowKind.SEED:
                    raise ValidationError(
                        "Seed windows cannot be disabled",
                        code=ErrorCode.DIALOG_WINDOW_NOT_DISABLEABLE,
                    )
            if data.banner_name_provided:
                # The same text can fit as a message and not as a photo caption,
                # and an empty one is fine only under a banner.
                await validate_stored_window_texts(
                    data.key,
                    data.banner_name,
                    self._translations_repository,
                    self._settings_repository,
                )
            window = await self._dialog_repository.update_window(
                data.key,
                UpdateDialogWindowDto(
                    banner_name=data.banner_name,
                    banner_name_provided=data.banner_name_provided,
                    is_enabled=data.is_enabled,
                    name=data.name,
                ),
            )
        await publish_dialog_change(self._redis)
        return window
