from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.admin import require_admin
from app.core.enums import Currency
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.advertising.api.schemas import (
    AdLinkPageResponse,
    AdLinkResponse,
    AdLinkStatsResponse,
    AttributedUserPageResponse,
    AttributedUserResponse,
    CreateAdLinkRequest,
    DailyAttributionCountResponse,
    GeneratedAdLinkCodeResponse,
    UpdateAdLinkRequest,
)
from app.modules.advertising.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    AdLinkDto,
    AttributedUserDto,
    CreateAdLinkDto,
    GetAdLinkStatsDto,
    ListAdLinkAttributedUsersDto,
    ListAdLinksDto,
    UpdateAdLinkDto,
)
from app.modules.advertising.usecases import (
    CreateAdLinkUseCase,
    DeleteAdLinkUseCase,
    GenerateAdLinkCodeUseCase,
    GetAdLinkStatsUseCase,
    ListAdLinkAttributedUsersUseCase,
    ListAdLinksUseCase,
    UpdateAdLinkUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/advertising", tags=["advertising"])


def _to_response(ad_link: AdLinkDto) -> AdLinkResponse:
    return AdLinkResponse(
        id=ad_link.id,
        name=ad_link.name,
        code=ad_link.code,
        cost=ad_link.cost,
        cost_currency=ad_link.cost_currency,
        is_active=ad_link.is_active,
        note=ad_link.note,
        created_by=ad_link.created_by,
        created_at=ad_link.created_at,
        updated_at=ad_link.updated_at,
    )


def _to_attributed_user_response(user: AttributedUserDto) -> AttributedUserResponse:
    return AttributedUserResponse(
        user_id=user.user_id,
        name=user.name,
        channel=user.channel,
        created_at=user.created_at,
        has_paid=user.has_paid,
    )


@router.get("/links", response_model=AdLinkPageResponse)
@inject
async def list_ad_links(
    use_case: FromDishka[ListAdLinksUseCase],
    actor: UserDto = Depends(require_admin),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> AdLinkPageResponse:
    ad_links, total = await use_case(
        actor, ListAdLinksDto(is_active=is_active, page=page, page_size=page_size)
    )
    return AdLinkPageResponse(items=[_to_response(link) for link in ad_links], total=total)


@router.post("/links", response_model=AdLinkResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_ad_link(
    payload: CreateAdLinkRequest,
    use_case: FromDishka[CreateAdLinkUseCase],
    actor: UserDto = Depends(require_admin),
) -> AdLinkResponse:
    try:
        ad_link = await use_case(
            actor,
            CreateAdLinkDto(
                name=payload.name,
                code=payload.code,
                cost=payload.cost,
                cost_currency=payload.cost_currency,
                note=payload.note,
                created_by=actor.id if actor.id > 0 else None,
            ),
        )
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_response(ad_link)


@router.patch("/links/{ad_link_id}", response_model=AdLinkResponse)
@inject
async def update_ad_link(
    ad_link_id: int,
    payload: UpdateAdLinkRequest,
    use_case: FromDishka[UpdateAdLinkUseCase],
    actor: UserDto = Depends(require_admin),
) -> AdLinkResponse:
    try:
        ad_link = await use_case(
            actor,
            UpdateAdLinkDto(
                ad_link_id=ad_link_id,
                name=payload.name,
                cost=payload.cost,
                cost_currency=payload.cost_currency,
                is_active=payload.is_active,
                note=payload.note,
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_response(ad_link)


@router.delete("/links/{ad_link_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_ad_link(
    ad_link_id: int,
    use_case: FromDishka[DeleteAdLinkUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, ad_link_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/links/generate-code", response_model=GeneratedAdLinkCodeResponse)
@inject
async def generate_ad_link_code(
    use_case: FromDishka[GenerateAdLinkCodeUseCase],
    actor: UserDto = Depends(require_admin),
) -> GeneratedAdLinkCodeResponse:
    return GeneratedAdLinkCodeResponse(code=await use_case(actor))


@router.get("/links/{ad_link_id}/stats", response_model=AdLinkStatsResponse)
@inject
async def get_ad_link_stats(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkStatsUseCase],
    actor: UserDto = Depends(require_admin),
    report_currency: Optional[Currency] = Query(None),
) -> AdLinkStatsResponse:
    try:
        stats = await use_case(
            actor, GetAdLinkStatsDto(ad_link_id=ad_link_id, report_currency=report_currency)
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return AdLinkStatsResponse(
        attributions_count=stats.attributions_count,
        attributions_by_channel=stats.attributions_by_channel,
        paid_count=stats.paid_count,
        conversion_rate=stats.conversion_rate,
        revenue=stats.revenue,
        revenue_by_currency=stats.revenue_by_currency,
        cost=stats.cost,
        report_currency=stats.report_currency,
        cpa=stats.cpa,
        roi=stats.roi,
        daily_registrations=[
            DailyAttributionCountResponse(day=row.day, count=row.count)
            for row in stats.daily_registrations
        ],
    )


@router.get("/links/{ad_link_id}/users", response_model=AttributedUserPageResponse)
@inject
async def list_ad_link_attributed_users(
    ad_link_id: int,
    use_case: FromDishka[ListAdLinkAttributedUsersUseCase],
    actor: UserDto = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> AttributedUserPageResponse:
    try:
        users, total = await use_case(
            actor,
            ListAdLinkAttributedUsersDto(ad_link_id=ad_link_id, page=page, page_size=page_size),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return AttributedUserPageResponse(
        items=[_to_attributed_user_response(user) for user in users], total=total
    )
