from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Body, Depends, File, Query, UploadFile, status

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import BroadcastRecipientStatus, BroadcastStatus
from app.modules.broadcasts.api.schemas import (
    AudiencePreviewResponse,
    BroadcastListResponse,
    BroadcastRecipientListResponse,
    BroadcastRecipientResponse,
    BroadcastRequest,
    BroadcastResponse,
    BroadcastSummaryResponse,
    PreviewAudienceRequest,
    SendBroadcastRequest,
)
from app.modules.broadcasts.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ListBroadcastRecipientsDto,
    ListBroadcastsDto,
    PreviewAudienceDto,
    SaveBroadcastDto,
    SendBroadcastDto,
    SetBroadcastMediaDto,
    UpdateBroadcastDto,
)
from app.modules.broadcasts.usecases import (
    CancelBroadcastUseCase,
    CreateBroadcastUseCase,
    DeleteBroadcastMediaUseCase,
    DeleteBroadcastUseCase,
    GetBroadcastSummaryUseCase,
    GetBroadcastUseCase,
    ListBroadcastRecipientsUseCase,
    ListBroadcastsUseCase,
    PreviewBroadcastAudienceUseCase,
    RecallBroadcastUseCase,
    RetryBroadcastUseCase,
    SendBroadcastUseCase,
    SendTestBroadcastUseCase,
    SetBroadcastMediaUseCase,
    UpdateBroadcastUseCase,
)
from app.modules.broadcasts.usecases.set_broadcast_media import MAX_MEDIA_SIZE_BYTES
from app.modules.users import UserDto

router = APIRouter(prefix="/broadcasts", tags=["broadcasts"])


def _save_dto(body: BroadcastRequest) -> SaveBroadcastDto:
    return SaveBroadcastDto(
        title=body.title,
        category=body.category,
        audience=body.audience,
        default_locale=body.default_locale,
        contents=body.contents,
        buttons=body.buttons,
        promocode_id=body.promocode_id,
        post_to_channel=body.post_to_channel,
    )


@router.get("", response_model=BroadcastListResponse, responses=error_responses(422))
@inject
async def list_broadcasts(
    use_case: FromDishka[ListBroadcastsUseCase],
    actor: Actor = Depends(require_admin),
    broadcast_statuses: list[BroadcastStatus] = Query([], alias="status"),
    search: Optional[str] = Query(None, max_length=200),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> BroadcastListResponse:
    items, total = await use_case(
        actor,
        ListBroadcastsDto(
            statuses=broadcast_statuses,
            search=search,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        ),
    )
    return BroadcastListResponse(
        items=[BroadcastResponse.model_validate(item, from_attributes=True) for item in items],
        total=total,
    )


@router.post(
    "",
    response_model=BroadcastResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 422),
)
@inject
async def create_broadcast(
    body: BroadcastRequest,
    use_case: FromDishka[CreateBroadcastUseCase],
    actor: Actor = Depends(require_admin),
) -> BroadcastResponse:
    return BroadcastResponse.model_validate(
        await use_case(actor, _save_dto(body)), from_attributes=True
    )


@router.post(
    "/actions/preview-audience",
    response_model=AudiencePreviewResponse,
    responses=error_responses(422),
)
@inject
async def preview_broadcast_audience(
    body: PreviewAudienceRequest,
    use_case: FromDishka[PreviewBroadcastAudienceUseCase],
    actor: Actor = Depends(require_admin),
) -> AudiencePreviewResponse:
    result = await use_case(
        actor, PreviewAudienceDto(audience=body.audience, category=body.category)
    )
    return AudiencePreviewResponse(total=result.total, by_locale=result.by_locale)


@router.get("/summary", response_model=BroadcastSummaryResponse, responses=error_responses(422))
@inject
async def get_broadcast_summary(
    use_case: FromDishka[GetBroadcastSummaryUseCase],
    actor: Actor = Depends(require_admin),
) -> BroadcastSummaryResponse:
    return BroadcastSummaryResponse.model_validate(
        await use_case(actor, None), from_attributes=True
    )


@router.get("/{broadcast_id:int}", response_model=BroadcastResponse, responses=error_responses(404))
@inject
async def get_broadcast(
    broadcast_id: int,
    use_case: FromDishka[GetBroadcastUseCase],
    actor: Actor = Depends(require_admin),
) -> BroadcastResponse:
    return BroadcastResponse.model_validate(
        await use_case(actor, broadcast_id), from_attributes=True
    )


@router.get(
    "/{broadcast_id:int}/recipients",
    response_model=BroadcastRecipientListResponse,
    responses=error_responses(404),
)
@inject
async def list_broadcast_recipients(
    broadcast_id: int,
    use_case: FromDishka[ListBroadcastRecipientsUseCase],
    actor: Actor = Depends(require_admin),
    recipient_status: Optional[BroadcastRecipientStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> BroadcastRecipientListResponse:
    items, total = await use_case(
        actor,
        ListBroadcastRecipientsDto(
            broadcast_id=broadcast_id, status=recipient_status, page=page, page_size=page_size
        ),
    )
    return BroadcastRecipientListResponse(
        items=[
            BroadcastRecipientResponse.model_validate(item, from_attributes=True) for item in items
        ],
        total=total,
    )


@router.put(
    "/{broadcast_id:int}",
    response_model=BroadcastResponse,
    responses=error_responses(404, 409, 422),
)
@inject
async def update_broadcast(
    broadcast_id: int,
    body: BroadcastRequest,
    use_case: FromDishka[UpdateBroadcastUseCase],
    actor: Actor = Depends(require_admin),
) -> BroadcastResponse:
    result = await use_case(
        actor, UpdateBroadcastDto(broadcast_id=broadcast_id, data=_save_dto(body))
    )
    return BroadcastResponse.model_validate(result, from_attributes=True)


@router.delete(
    "/{broadcast_id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404, 409),
)
@inject
async def delete_broadcast(
    broadcast_id: int,
    use_case: FromDishka[DeleteBroadcastUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, broadcast_id)


@router.put(
    "/{broadcast_id:int}/media",
    response_model=BroadcastResponse,
    responses=error_responses(404, 409, 422),
)
@inject
async def upload_broadcast_media(
    broadcast_id: int,
    use_case: FromDishka[SetBroadcastMediaUseCase],
    actor: Actor = Depends(require_admin),
    file: UploadFile = File(...),
) -> BroadcastResponse:
    # bounded read: an oversized upload is rejected before it's buffered
    data = await file.read(MAX_MEDIA_SIZE_BYTES + 1)
    result = await use_case(
        actor,
        SetBroadcastMediaDto(
            broadcast_id=broadcast_id,
            content_type=file.content_type or "",
            filename=file.filename or "",
            data=data,
        ),
    )
    return BroadcastResponse.model_validate(result, from_attributes=True)


@router.delete(
    "/{broadcast_id:int}/media",
    response_model=BroadcastResponse,
    responses=error_responses(404, 409),
)
@inject
async def delete_broadcast_media(
    broadcast_id: int,
    use_case: FromDishka[DeleteBroadcastMediaUseCase],
    actor: Actor = Depends(require_admin),
) -> BroadcastResponse:
    return BroadcastResponse.model_validate(
        await use_case(actor, broadcast_id), from_attributes=True
    )


@router.post(
    "/{broadcast_id:int}/actions/send-test",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404, 422),
)
@inject
async def send_test_broadcast(
    broadcast_id: int,
    use_case: FromDishka[SendTestBroadcastUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(actor, broadcast_id)


@router.post(
    "/{broadcast_id:int}/actions/send",
    response_model=BroadcastResponse,
    responses=error_responses(404, 409, 422),
)
@inject
async def send_broadcast(
    broadcast_id: int,
    use_case: FromDishka[SendBroadcastUseCase],
    actor: Actor = Depends(require_admin),
    body: SendBroadcastRequest = Body(default_factory=SendBroadcastRequest),
) -> BroadcastResponse:
    result = await use_case(
        actor, SendBroadcastDto(broadcast_id=broadcast_id, scheduled_at=body.scheduled_at)
    )
    return BroadcastResponse.model_validate(result, from_attributes=True)


@router.post(
    "/{broadcast_id:int}/actions/cancel",
    response_model=BroadcastResponse,
    responses=error_responses(404, 409),
)
@inject
async def cancel_broadcast(
    broadcast_id: int,
    use_case: FromDishka[CancelBroadcastUseCase],
    actor: Actor = Depends(require_admin),
) -> BroadcastResponse:
    return BroadcastResponse.model_validate(
        await use_case(actor, broadcast_id), from_attributes=True
    )


@router.post(
    "/{broadcast_id:int}/actions/retry",
    response_model=BroadcastResponse,
    responses=error_responses(404, 409),
)
@inject
async def retry_broadcast(
    broadcast_id: int,
    use_case: FromDishka[RetryBroadcastUseCase],
    actor: Actor = Depends(require_admin),
) -> BroadcastResponse:
    return BroadcastResponse.model_validate(
        await use_case(actor, broadcast_id), from_attributes=True
    )


@router.post(
    "/{broadcast_id:int}/actions/recall",
    response_model=BroadcastResponse,
    responses=error_responses(404, 409),
)
@inject
async def recall_broadcast(
    broadcast_id: int,
    use_case: FromDishka[RecallBroadcastUseCase],
    actor: Actor = Depends(require_admin),
) -> BroadcastResponse:
    return BroadcastResponse.model_validate(
        await use_case(actor, broadcast_id), from_attributes=True
    )
