from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin
from app.core.constants import INT32_MAX
from app.core.events import EventCategory
from app.core.utils.time import range_end_utc, range_start_utc
from app.modules.event_log.api.schemas import (
    EventLogEntryResponse,
    EventLogPageResponse,
    NotificationGroupsResponse,
    NotificationsResponse,
    UpdateNotificationGroupsRequest,
)
from app.modules.event_log.dto import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, NOTIFICATION_GROUPS
from app.modules.event_log.usecases import (
    GetNotificationGroupsUseCase,
    GetNotificationsUseCase,
    ListEventLogInput,
    ListEventLogUseCase,
    MarkNotificationsReadUseCase,
    UpdateNotificationGroupsUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/event-log", tags=["event-log"])


@router.get("", response_model=EventLogPageResponse)
@inject
async def list_event_log(
    use_case: FromDishka[ListEventLogUseCase],
    actor: UserDto = Depends(require_admin),
    category: Optional[EventCategory] = None,
    actor_id: Optional[int] = Query(None, ge=1, le=INT32_MAX),
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> EventLogPageResponse:
    items, total = await use_case(
        actor,
        ListEventLogInput(
            category=category,
            actor_id=actor_id,
            search=search,
            date_from=range_start_utc(date_from),
            date_to=range_end_utc(date_to),
            page=page,
            page_size=page_size,
        ),
    )
    return EventLogPageResponse(
        items=[EventLogEntryResponse.model_validate(i, from_attributes=True) for i in items],
        total=total,
    )


@router.get("/notifications", response_model=NotificationsResponse)
@inject
async def get_notifications(
    use_case: FromDishka[GetNotificationsUseCase],
    actor: UserDto = Depends(require_admin),
) -> NotificationsResponse:
    notifications = await use_case(actor)
    return NotificationsResponse(
        items=[
            EventLogEntryResponse.model_validate(i, from_attributes=True)
            for i in notifications.items
        ],
        unread_count=notifications.unread_count,
    )


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def mark_notifications_read(
    use_case: FromDishka[MarkNotificationsReadUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    await use_case(actor)


@router.get("/notifications/groups", response_model=NotificationGroupsResponse)
@inject
async def get_notification_groups(
    use_case: FromDishka[GetNotificationGroupsUseCase],
    actor: UserDto = Depends(require_admin),
) -> NotificationGroupsResponse:
    groups = await use_case(actor)
    return NotificationGroupsResponse(groups=groups, available=list(NOTIFICATION_GROUPS))


@router.put("/notifications/groups", response_model=NotificationGroupsResponse)
@inject
async def update_notification_groups(
    body: UpdateNotificationGroupsRequest,
    use_case: FromDishka[UpdateNotificationGroupsUseCase],
    actor: UserDto = Depends(require_admin),
) -> NotificationGroupsResponse:
    groups = await use_case(actor, body.groups)
    return NotificationGroupsResponse(groups=groups, available=list(NOTIFICATION_GROUPS))
