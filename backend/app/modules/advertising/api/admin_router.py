from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.enums import AdLinkChannel
from app.core.utils.time import range_end_utc, range_start_utc
from app.modules.advertising.api.schemas import (
    AdLinkPageResponse,
    AdLinkPayoutResponse,
    AdLinkResponse,
    AdLinkShareUrlsResponse,
    AdLinkStatsResponse,
    AdvertisingSummaryResponse,
    AttributedUserPageResponse,
    AttributedUserResponse,
    CreateAdLinkRequest,
    GeneratedAdLinkCodeResponse,
    UpdateAdLinkRequest,
    UserAdAttributionResponse,
)
from app.modules.advertising.dto import (
    CreateAdLinkDto,
    GetAdLinkPayoutDto,
    GetAdLinkStatsDto,
    GetAdvertisingSummaryDto,
    ListAdLinkAttributedUsersDto,
    ListAdLinksDto,
    UpdateAdLinkDto,
)
from app.modules.advertising.qr import render_share_qr
from app.modules.advertising.usecases import (
    CreateAdLinkUseCase,
    DeleteAdLinkUseCase,
    GenerateAdLinkCodeUseCase,
    GetAdLinkPayoutUseCase,
    GetAdLinkShareUrlsUseCase,
    GetAdLinkStatsUseCase,
    GetAdLinkUseCase,
    GetAdvertisingSummaryUseCase,
    GetUserAdAttributionUseCase,
    ListAdLinkAttributedUsersUseCase,
    ListAdLinksUseCase,
    UpdateAdLinkUseCase,
)

router = APIRouter(prefix="/advertising", tags=["advertising"])
user_router = APIRouter(prefix="/users", tags=["advertising"])


@router.get("/links", response_model=AdLinkPageResponse)
@inject
async def list_ad_links(
    use_case: FromDishka[ListAdLinksUseCase],
    actor: Actor = Depends(require_admin),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> AdLinkPageResponse:
    ad_links, total = await use_case(
        actor, ListAdLinksDto(is_active=is_active, page=page, page_size=page_size)
    )
    return AdLinkPageResponse(
        items=[AdLinkResponse.model_validate(link, from_attributes=True) for link in ad_links],
        total=total,
    )


@router.post(
    "/links",
    response_model=AdLinkResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 409),
)
@inject
async def create_ad_link(
    payload: CreateAdLinkRequest,
    use_case: FromDishka[CreateAdLinkUseCase],
    actor: Actor = Depends(require_admin),
) -> AdLinkResponse:
    ad_link = await use_case(
        actor,
        CreateAdLinkDto(
            name=payload.name,
            code=payload.code,
            cost=payload.cost,
            cost_currency=payload.cost_currency,
            revenue_share_percent=payload.revenue_share_percent,
            allow_bot=payload.allow_bot,
            allow_webcabinet=payload.allow_webcabinet,
            note=payload.note,
        ),
    )
    return AdLinkResponse.model_validate(ad_link, from_attributes=True)


@router.patch(
    "/links/{ad_link_id:int}", response_model=AdLinkResponse, responses=error_responses(400, 404)
)
@inject
async def update_ad_link(
    ad_link_id: int,
    payload: UpdateAdLinkRequest,
    use_case: FromDishka[UpdateAdLinkUseCase],
    actor: Actor = Depends(require_admin),
) -> AdLinkResponse:
    ad_link = await use_case(
        actor,
        UpdateAdLinkDto(
            ad_link_id=ad_link_id,
            name=payload.name,
            cost=payload.cost,
            cost_currency=payload.cost_currency,
            revenue_share_percent=payload.revenue_share_percent,
            is_active=payload.is_active,
            allow_bot=payload.allow_bot,
            allow_webcabinet=payload.allow_webcabinet,
            note=payload.note,
        ),
    )
    return AdLinkResponse.model_validate(ad_link, from_attributes=True)


@router.delete(
    "/links/{ad_link_id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404, 409),
)
@inject
async def delete_ad_link(
    ad_link_id: int,
    use_case: FromDishka[DeleteAdLinkUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, ad_link_id)


@router.post("/links/actions/generate-code", response_model=GeneratedAdLinkCodeResponse)
@inject
async def generate_ad_link_code(
    use_case: FromDishka[GenerateAdLinkCodeUseCase],
    actor: Actor = Depends(require_admin),
) -> GeneratedAdLinkCodeResponse:
    return GeneratedAdLinkCodeResponse(code=await use_case(actor))


@router.get(
    "/links/{ad_link_id:int}/stats",
    response_model=AdLinkStatsResponse,
    responses=error_responses(404),
)
@inject
async def get_ad_link_stats(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkStatsUseCase],
    actor: Actor = Depends(require_admin),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
) -> AdLinkStatsResponse:
    stats = await use_case(
        actor,
        GetAdLinkStatsDto(
            ad_link_id=ad_link_id,
            created_from=range_start_utc(created_from),
            created_to=range_end_utc(created_to),
        ),
    )
    return AdLinkStatsResponse.model_validate(stats, from_attributes=True)


@router.get(
    "/links/{ad_link_id:int}/payout",
    response_model=AdLinkPayoutResponse,
    responses=error_responses(404),
)
@inject
async def get_ad_link_payout(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkPayoutUseCase],
    paid_from: datetime = Query(),
    paid_to: datetime = Query(),
    actor: Actor = Depends(require_admin),
) -> AdLinkPayoutResponse:
    payout = await use_case(
        actor,
        GetAdLinkPayoutDto(
            ad_link_id=ad_link_id,
            paid_from=range_start_utc(paid_from),
            paid_to=range_end_utc(paid_to),
        ),
    )
    return AdLinkPayoutResponse.model_validate(payout, from_attributes=True)


@router.get(
    "/links/{ad_link_id:int}/share",
    response_model=AdLinkShareUrlsResponse,
    responses=error_responses(404),
)
@inject
async def get_ad_link_share_urls(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkShareUrlsUseCase],
    actor: Actor = Depends(require_admin),
) -> AdLinkShareUrlsResponse:
    urls = await use_case(actor, ad_link_id)
    return AdLinkShareUrlsResponse.model_validate(urls, from_attributes=True)


@router.get("/links/{ad_link_id:int}/qr", response_class=Response, responses=error_responses(404))
@inject
async def get_ad_link_qr(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkShareUrlsUseCase],
    actor: Actor = Depends(require_admin),
    channel: AdLinkChannel = Query(AdLinkChannel.BOT),
) -> Response:
    png = render_share_qr(await use_case(actor, ad_link_id), channel)
    return Response(content=png, media_type="image/png")


@router.get("/summary", response_model=AdvertisingSummaryResponse)
@inject
async def get_advertising_summary(
    use_case: FromDishka[GetAdvertisingSummaryUseCase],
    actor: Actor = Depends(require_admin),
    is_active: Optional[bool] = Query(None),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
) -> AdvertisingSummaryResponse:
    summary = await use_case(
        actor,
        GetAdvertisingSummaryDto(
            is_active=is_active,
            created_from=range_start_utc(created_from),
            created_to=range_end_utc(created_to),
        ),
    )
    return AdvertisingSummaryResponse.model_validate(summary, from_attributes=True)


@router.get(
    "/links/{ad_link_id:int}/users",
    response_model=AttributedUserPageResponse,
    responses=error_responses(404),
)
@inject
async def list_ad_link_attributed_users(
    ad_link_id: int,
    use_case: FromDishka[ListAdLinkAttributedUsersUseCase],
    actor: Actor = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> AttributedUserPageResponse:
    users, total = await use_case(
        actor,
        ListAdLinkAttributedUsersDto(ad_link_id=ad_link_id, page=page, page_size=page_size),
    )
    return AttributedUserPageResponse(
        items=[AttributedUserResponse.model_validate(user, from_attributes=True) for user in users],
        total=total,
    )


@user_router.get(
    "/{user_id:int}/ad-attribution",
    response_model=UserAdAttributionResponse,
    responses=error_responses(404),
)
@inject
async def get_user_ad_attribution(
    user_id: int,
    use_case: FromDishka[GetUserAdAttributionUseCase],
    actor: Actor = Depends(require_admin),
) -> UserAdAttributionResponse:
    attribution = await use_case(actor, user_id)
    return UserAdAttributionResponse.model_validate(
        {"attribution": attribution}, from_attributes=True
    )


@router.get(
    "/links/{ad_link_id:int}", response_model=AdLinkResponse, responses=error_responses(404)
)
@inject
async def get_ad_link(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkUseCase],
    actor: Actor = Depends(require_admin),
) -> AdLinkResponse:
    return AdLinkResponse.model_validate(await use_case(actor, ad_link_id), from_attributes=True)
