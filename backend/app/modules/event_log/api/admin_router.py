from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, INT32_MAX, MAX_PAGE_SIZE, SEARCH_MAX_LENGTH
from app.core.events import EventCategory
from app.core.utils.time import range_end_utc, range_start_utc
from app.modules.event_log.api.schemas import (
    EventLogEntryResponse,
    EventLogPageResponse,
    NotificationsResponse,
)
from app.modules.event_log.dto import ListEventLogDto
from app.modules.event_log.usecases import (
    ClearNotificationsUseCase,
    GetEventLogEntryUseCase,
    GetNotificationsUseCase,
    ListEventLogUseCase,
    MarkNotificationsReadUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=EventLogPageResponse)
@inject
async def list_event_log(
    use_case: FromDishka[ListEventLogUseCase],
    actor: Actor = Depends(require_admin),
    category: Optional[EventCategory] = None,
    actor_id: Optional[int] = Query(None, ge=1, le=INT32_MAX),
    target_id: Optional[int] = Query(None, ge=1, le=INT32_MAX),
    event_type: Optional[str] = Query(None, max_length=128),
    search: Optional[str] = Query(None, max_length=SEARCH_MAX_LENGTH),
    occurred_from: Optional[datetime] = None,
    occurred_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> EventLogPageResponse:
    items, total = await use_case(
        actor,
        ListEventLogDto(
            category=category,
            actor_id=actor_id,
            target_id=target_id,
            event_type=event_type,
            search=search,
            occurred_from=range_start_utc(occurred_from),
            occurred_to=range_end_utc(occurred_to),
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
    actor: UserDto = Depends(require_admin_user),
) -> NotificationsResponse:
    notifications = await use_case(actor)
    items = [
        EventLogEntryResponse.model_validate(i, from_attributes=True) for i in notifications.items
    ]
    return NotificationsResponse(
        items=items, total=len(items), unread_count=notifications.unread_count
    )


@router.post("/notifications/actions/mark-read", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def mark_notifications_read(
    use_case: FromDishka[MarkNotificationsReadUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(actor)


@router.post("/notifications/actions/clear", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def clear_notifications(
    use_case: FromDishka[ClearNotificationsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(actor)


@router.get("/{entry_id:int}", response_model=EventLogEntryResponse, responses=error_responses(404))
@inject
async def get_event_log_entry(
    entry_id: int,
    use_case: FromDishka[GetEventLogEntryUseCase],
    actor: Actor = Depends(require_admin),
) -> EventLogEntryResponse:
    return EventLogEntryResponse.model_validate(
        await use_case(actor, entry_id), from_attributes=True
    )
