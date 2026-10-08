from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.modules.account_merge.api.schemas import (
    MergeAccountsRequest,
    MergePreviewResponse,
)
from app.modules.account_merge.dto import GetMergePreviewDto, MergeAccountsDto
from app.modules.account_merge.usecases import GetMergePreviewUseCase, MergeAccountsUseCase
from app.modules.users import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/{user_id:int}/merge-preview",
    response_model=MergePreviewResponse,
    responses=error_responses(400, 404),
)
@inject
async def get_merge_preview(
    user_id: int,
    use_case: FromDishka[GetMergePreviewUseCase],
    source_id: int = Query(),
    actor: Actor = Depends(require_admin),
) -> MergePreviewResponse:
    preview = await use_case(actor, GetMergePreviewDto(target_id=user_id, source_id=source_id))
    return MergePreviewResponse.model_validate(preview, from_attributes=True)


@router.post(
    "/{user_id:int}/actions/merge", response_model=UserResponse, responses=error_responses(400, 404)
)
@inject
async def merge_users(
    user_id: int,
    payload: MergeAccountsRequest,
    use_case: FromDishka[MergeAccountsUseCase],
    actor: Actor = Depends(require_admin),
) -> UserResponse:
    merged = await use_case(
        actor,
        MergeAccountsDto(
            target_id=user_id,
            source_id=payload.source_id,
            choices=payload.choices,
            fingerprint=payload.fingerprint,
        ),
    )
    return UserResponse.model_validate(merged, from_attributes=True)
