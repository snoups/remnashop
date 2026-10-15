from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SEARCH_MAX_LENGTH
from app.core.enums import PromocodeRewardType, PromocodeStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.promocodes.api.schemas import (
    CreatePromocodeRequest,
    GeneratedPromocodeCodeResponse,
    PromocodeActivatedUserPageResponse,
    PromocodeActivatedUserResponse,
    PromocodePageResponse,
    PromocodeResponse,
    PromocodeSummaryResponse,
    UpdatePromocodeRequest,
    UserPromocodeActivationListResponse,
    UserPromocodeActivationResponse,
)
from app.modules.promocodes.dto import (
    CreatePromocodeDto,
    ListPromocodeActivatedUsersDto,
    ListPromocodesDto,
    UpdatePromocodeDto,
)
from app.modules.promocodes.usecases import (
    CreatePromocodeUseCase,
    DeletePromocodeUseCase,
    GeneratePromocodeCodeUseCase,
    GetPromocodeSummaryUseCase,
    GetPromocodeUseCase,
    ListPromocodeActivatedUsersUseCase,
    ListPromocodesUseCase,
    ListUserPromocodeActivationsUseCase,
    UpdatePromocodeUseCase,
)

router = APIRouter(prefix="/promocodes", tags=["promocodes"])
user_router = APIRouter(prefix="/users", tags=["promocodes"])


@router.get("", response_model=PromocodePageResponse)
@inject
async def list_promocodes(
    use_case: FromDishka[ListPromocodesUseCase],
    actor: Actor = Depends(require_admin),
    promocode_status: Optional[PromocodeStatus] = Query(None, alias="status"),
    reward_type: Optional[PromocodeRewardType] = Query(None),
    search: Optional[str] = Query(None, max_length=SEARCH_MAX_LENGTH),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PromocodePageResponse:
    promocodes, total = await use_case(
        actor,
        ListPromocodesDto(
            status=promocode_status,
            reward_type=reward_type,
            search=search,
            page=page,
            page_size=page_size,
        ),
    )
    return PromocodePageResponse(
        items=[
            PromocodeResponse.model_validate(promo, from_attributes=True) for promo in promocodes
        ],
        total=total,
    )


@user_router.get(
    "/{user_id:int}/promocode-activations",
    response_model=UserPromocodeActivationListResponse,
    responses=error_responses(404),
)
@inject
async def list_user_promocode_activations(
    user_id: int,
    use_case: FromDishka[ListUserPromocodeActivationsUseCase],
    actor: Actor = Depends(require_admin),
) -> UserPromocodeActivationListResponse:
    activations = await use_case(actor, user_id)
    items = [
        UserPromocodeActivationResponse.model_validate(item, from_attributes=True)
        for item in activations
    ]
    return UserPromocodeActivationListResponse(items=items, total=len(items))


@router.get("/summary", response_model=PromocodeSummaryResponse)
@inject
async def get_promocode_summary(
    use_case: FromDishka[GetPromocodeSummaryUseCase],
    actor: Actor = Depends(require_admin),
) -> PromocodeSummaryResponse:
    return PromocodeSummaryResponse.model_validate(await use_case(actor), from_attributes=True)


@router.get(
    "/{promocode_id:int}/users",
    response_model=PromocodeActivatedUserPageResponse,
    responses=error_responses(404),
)
@inject
async def list_promocode_activated_users(
    promocode_id: int,
    use_case: FromDishka[ListPromocodeActivatedUsersUseCase],
    actor: Actor = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PromocodeActivatedUserPageResponse:
    users, total = await use_case(
        actor,
        ListPromocodeActivatedUsersDto(promocode_id=promocode_id, page=page, page_size=page_size),
    )
    return PromocodeActivatedUserPageResponse(
        items=[
            PromocodeActivatedUserResponse.model_validate(user, from_attributes=True)
            for user in users
        ],
        total=total,
    )


@router.post(
    "",
    response_model=PromocodeResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 409),
)
@inject
async def create_promocode(
    payload: CreatePromocodeRequest,
    use_case: FromDishka[CreatePromocodeUseCase],
    actor: Actor = Depends(require_admin),
) -> PromocodeResponse:
    try:
        promo = await use_case(
            actor,
            CreatePromocodeDto(
                code=payload.code,
                reward_type=payload.reward_type,
                reward=payload.reward,
                reward_addon_id=payload.reward_addon_id,
                reward_plan_id=payload.reward_plan_id,
                reward_duration_days=payload.reward_duration_days,
                availability=payload.availability,
                allowed_user_ids=payload.allowed_user_ids,
                allowed_plan_ids=payload.allowed_plan_ids,
                expires_at=payload.expires_at,
                max_activations=payload.max_activations,
                is_reusable=payload.is_reusable,
            ),
        )
    except NotFoundError as error:
        # a referenced plan or add-on that doesn't exist is a bad body, not a missing route
        raise ValidationError(str(error), code=error.code) from error
    return PromocodeResponse.model_validate(promo, from_attributes=True)


@router.patch(
    "/{promocode_id:int}", response_model=PromocodeResponse, responses=error_responses(400, 404)
)
@inject
async def update_promocode(
    promocode_id: int,
    payload: UpdatePromocodeRequest,
    use_case: FromDishka[UpdatePromocodeUseCase],
    actor: Actor = Depends(require_admin),
) -> PromocodeResponse:
    promo = await use_case(
        actor,
        UpdatePromocodeDto(
            promocode_id=promocode_id,
            is_active=payload.is_active,
            availability=payload.availability,
            allowed_user_ids=payload.allowed_user_ids,
            allowed_plan_ids=payload.allowed_plan_ids,
            expires_at=payload.expires_at,
            max_activations=payload.max_activations,
            is_reusable=payload.is_reusable,
        ),
    )
    return PromocodeResponse.model_validate(promo, from_attributes=True)


@router.delete(
    "/{promocode_id:int}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def delete_promocode(
    promocode_id: int,
    use_case: FromDishka[DeletePromocodeUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, promocode_id)


@router.post("/actions/generate-code", response_model=GeneratedPromocodeCodeResponse)
@inject
async def generate_promocode_code(
    use_case: FromDishka[GeneratePromocodeCodeUseCase],
    actor: Actor = Depends(require_admin),
) -> GeneratedPromocodeCodeResponse:
    return GeneratedPromocodeCodeResponse(code=await use_case(actor))


@router.get("/{promocode_id:int}", response_model=PromocodeResponse, responses=error_responses(404))
@inject
async def get_promocode(
    promocode_id: int,
    use_case: FromDishka[GetPromocodeUseCase],
    actor: Actor = Depends(require_admin),
) -> PromocodeResponse:
    return PromocodeResponse.model_validate(
        await use_case(actor, promocode_id), from_attributes=True
    )
