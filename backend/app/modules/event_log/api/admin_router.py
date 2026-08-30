from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.api.dependencies.admin import require_admin
from app.core.events import EventCategory
from app.core.utils.time import range_end_utc, range_start_utc
from app.modules.event_log.api.schemas import EventLogEntryResponse, EventLogPageResponse
from app.modules.event_log.dto import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.modules.event_log.usecases import ListEventLogInput, ListEventLogUseCase
from app.modules.users import UserDto

router = APIRouter(prefix="/event-log", tags=["event-log"])


@router.get("", response_model=EventLogPageResponse)
@inject
async def list_event_log(
    use_case: FromDishka[ListEventLogUseCase],
    actor: UserDto = Depends(require_admin),
    category: Optional[EventCategory] = None,
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
