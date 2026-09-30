from dataclasses import asdict

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.utils.time import range_start_utc
from app.modules.promocodes.api.schemas import (
    CreatePromocodeRequest,
    GeneratedPromocodeCodeResponse,
    PromocodeActivatedUserPageResponse,
    PromocodeActivatedUserResponse,
    PromocodeResponse,
    PromocodeSummaryResponse,
    UpdatePromocodeRequest,
    UserPromocodeActivationResponse,
)
from app.modules.promocodes.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    CreatePromocodeDto,
    ListPromocodeActivatedUsersDto,
    PromocodeDto,
    UpdatePromocodeDto,
)
from app.modules.promocodes.usecases import (
    CreatePromocodeUseCase,
    DeletePromocodeUseCase,
    GeneratePromocodeCodeUseCase,
    GetPromocodeSummaryUseCase,
    ListPromocodeActivatedUsersUseCase,
    ListPromocodesUseCase,
    ListUserPromocodeActivationsUseCase,
    UpdatePromocodeUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/promocodes", tags=["promocodes"])


def _to_response(promo: PromocodeDto) -> PromocodeResponse:
    return PromocodeResponse(
        id=promo.id,
        code=promo.code,
        is_active=promo.is_active,
        reward_type=promo.reward_type,
        reward=promo.reward,
        reward_addon_id=promo.reward_addon_id,
        reward_plan_id=promo.reward_plan_id,
        reward_duration_days=promo.reward_duration_days,
        availability=promo.availability,
        allowed_user_ids=promo.allowed_user_ids,
        expires_at=promo.expires_at,
        max_activations=promo.max_activations,
        is_reusable=promo.is_reusable,
        created_at=promo.created_at,
    )


@router.get("", response_model=list[PromocodeResponse])
@inject
async def list_promocodes(
    use_case: FromDishka[ListPromocodesUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[PromocodeResponse]:
    promocodes = await use_case(actor)
    return [_to_response(promo) for promo in promocodes]


@router.get("/activations", response_model=list[UserPromocodeActivationResponse])
@inject
async def list_user_promocode_activations(
    user_id: int,
    use_case: FromDishka[ListUserPromocodeActivationsUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[UserPromocodeActivationResponse]:
    activations = await use_case(actor, user_id)
    return [UserPromocodeActivationResponse(**asdict(item)) for item in activations]


@router.get("/summary", response_model=PromocodeSummaryResponse)
@inject
async def get_promocode_summary(
    use_case: FromDishka[GetPromocodeSummaryUseCase],
    actor: UserDto = Depends(require_admin),
) -> PromocodeSummaryResponse:
    return PromocodeSummaryResponse(**asdict(await use_case(actor)))


@router.get("/{promocode_id}/users", response_model=PromocodeActivatedUserPageResponse)
@inject
async def list_promocode_activated_users(
    promocode_id: int,
    use_case: FromDishka[ListPromocodeActivatedUsersUseCase],
    actor: UserDto = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PromocodeActivatedUserPageResponse:
    try:
        users, total = await use_case(
            actor,
            ListPromocodeActivatedUsersDto(
                promocode_id=promocode_id, page=page, page_size=page_size
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return PromocodeActivatedUserPageResponse(
        items=[PromocodeActivatedUserResponse(**asdict(user)) for user in users], total=total
    )


@router.post("", response_model=PromocodeResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_promocode(
    payload: CreatePromocodeRequest,
    use_case: FromDishka[CreatePromocodeUseCase],
    actor: UserDto = Depends(require_admin),
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
                expires_at=range_start_utc(payload.expires_at),
                max_activations=payload.max_activations,
                is_reusable=payload.is_reusable,
            ),
        )
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except (NotFoundError, ValidationError) as error:
        # NotFoundError here means a bad reward_addon_id/reward_plan_id reference in
        # the body, not a missing URL resource -- unlike update/delete below, 404.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(promo)


@router.patch("/{promocode_id}", response_model=PromocodeResponse)
@inject
async def update_promocode(
    promocode_id: int,
    payload: UpdatePromocodeRequest,
    use_case: FromDishka[UpdatePromocodeUseCase],
    actor: UserDto = Depends(require_admin),
) -> PromocodeResponse:
    try:
        promo = await use_case(
            actor,
            UpdatePromocodeDto(
                promocode_id=promocode_id,
                is_active=payload.is_active,
                availability=payload.availability,
                allowed_user_ids=payload.allowed_user_ids,
                expires_at=range_start_utc(payload.expires_at),
                max_activations=payload.max_activations,
                is_reusable=payload.is_reusable,
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(promo)


@router.delete("/{promocode_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_promocode(
    promocode_id: int,
    use_case: FromDishka[DeletePromocodeUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, promocode_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/generate-code", response_model=GeneratedPromocodeCodeResponse)
@inject
async def generate_promocode_code(
    use_case: FromDishka[GeneratePromocodeCodeUseCase],
    actor: UserDto = Depends(require_admin),
) -> GeneratedPromocodeCodeResponse:
    return GeneratedPromocodeCodeResponse(code=await use_case(actor))
