from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.admin import require_admin_user
from app.modules.announcements.api.schemas import (
    AnnouncementIdsRequest,
    AnnouncementListResponse,
    AnnouncementResponse,
)
from app.modules.announcements.dto import AnnouncementIdsDto
from app.modules.announcements.usecases import (
    DismissAnnouncementsUseCase,
    ListAnnouncementsUseCase,
    MarkAnnouncementsSeenUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("", response_model=AnnouncementListResponse)
@inject
async def list_announcements(
    use_case: FromDishka[ListAnnouncementsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> AnnouncementListResponse:
    items = await use_case(actor)
    return AnnouncementListResponse(
        items=[AnnouncementResponse.model_validate(i, from_attributes=True) for i in items],
        total=len(items),
    )


@router.post("/actions/mark-seen", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def mark_announcements_seen(
    body: AnnouncementIdsRequest,
    use_case: FromDishka[MarkAnnouncementsSeenUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(actor, AnnouncementIdsDto(ids=body.ids))


@router.post("/actions/dismiss", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def dismiss_announcements(
    body: AnnouncementIdsRequest,
    use_case: FromDishka[DismissAnnouncementsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(actor, AnnouncementIdsDto(ids=body.ids))
