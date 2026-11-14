from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.customer_notifications.dto import (
    FEED_LIMIT,
    FEED_RETENTION,
    CustomerFeedDto,
    CustomerFeedItemDto,
)
from app.modules.customer_notifications.links import customer_url
from app.modules.customer_notifications.render_args import customer_render_args
from app.modules.customer_notifications.repository import CustomerNotificationRepository
from app.modules.notifications import NotificationRendererFactory
from app.modules.users import UserDto


class GetCustomerFeedUseCase(UseCase[None, CustomerFeedDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        repository: CustomerNotificationRepository,
        renderer_factory: NotificationRendererFactory,
        uow: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._renderer_factory = renderer_factory
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> CustomerFeedDto:
        since = datetime_now() - FEED_RETENTION
        async with self._uow:
            rows = await self._repository.list_recent(actor.id, since=since, limit=FEED_LIMIT)
            unread = await self._repository.count_unread(actor.id, since=since)
        renderer = await self._renderer_factory.build()
        items = []
        for row in rows:
            title, body = renderer.render(
                actor.language,
                f"Customer{row.event_type}",
                customer_render_args(row.args, actor.language, row.event_type),
            )
            if not body:  # the event type lost its translation
                continue
            items.append(
                CustomerFeedItemDto(
                    id=row.id,
                    event_type=row.event_type,
                    title=title,
                    body=body,
                    url=customer_url(row.event_type, row.subscription_id, row.args),
                    created_at=row.created_at,
                    read=row.read_at is not None,
                )
            )
        return CustomerFeedDto(items=items, unread_count=unread)
