from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import NotificationSettingsDto
from app.modules.notifications.events import VapidKeysGeneratedEvent
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.vapid import generate_vapid_keypair


class GenerateVapidKeysUseCase(UseCase[None, NotificationSettingsDto]):
    required_permission = Permission.NOTIFICATION_VAPID_KEYS_GENERATE

    def __init__(
        self,
        notification_repository: NotificationRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._notification_repository = notification_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> NotificationSettingsDto:
        public_key, private_key = generate_vapid_keypair()
        async with self._uow:
            # endpoints minted for the old key reject pushes signed with the new one
            removed = await self._notification_repository.delete_all_push_subscriptions()
            settings = await self._notification_repository.set_vapid_keys(public_key, private_key)
            await self._event_publisher.publish(
                VapidKeysGeneratedEvent(actor=actor, subscriptions_removed=removed)
            )
        return settings
