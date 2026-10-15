from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.events import changed_fields
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import ShopSettingsDto, UpdateShopSettingsDto
from app.modules.settings.events import ShopSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


class UpdateShopSettingsUseCase(UseCase[UpdateShopSettingsDto, ShopSettingsDto]):
    required_permission = Permission.SHOP_SETTINGS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateShopSettingsDto) -> ShopSettingsDto:
        if data.max_active_subscriptions is not None and data.max_active_subscriptions < 1:
            raise ValidationError(
                "max_active_subscriptions must be positive, or null for unlimited",
                code=ErrorCode.SHOP_SUBSCRIPTION_LIMIT_INVALID,
            )

        async with self._uow:
            before = await self._settings_repository.get_shop_settings()
            settings = await self._settings_repository.update_shop_settings(data)
            await self._event_publisher.publish(
                ShopSettingsChangedEvent(
                    actor=actor, changed_fields=changed_fields(before, settings, data.fields_set)
                )
            )
        logger.info(f"{actor.log} Updated shop settings")
        return settings
