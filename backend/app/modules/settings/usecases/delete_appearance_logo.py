from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageKind
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.appearance_images import remove_appearance_image
from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.repository import SettingsRepository


class DeleteAppearanceLogoUseCase(UseCase[None, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_LOGO_DELETE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        config: AppConfig,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> AppearanceSettingsDto:
        return await remove_appearance_image(
            self._settings_repository,
            self._config,
            self._uow,
            self._event_publisher,
            actor,
            AppearanceImageKind.LOGO,
        )
