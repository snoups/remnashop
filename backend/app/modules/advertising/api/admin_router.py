from dataclasses import asdict
from datetime import datetime
from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import AdLinkChannel, Currency
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.advertising.api.schemas import (
    AdLinkMetricsResponse,
    AdLinkPageResponse,
    AdLinkResponse,
    AdLinkShareUrlsResponse,
    AdLinkStatsResponse,
    AdvertisingSummaryResponse,
    AttributedUserPageResponse,
    AttributedUserResponse,
    CreateAdLinkRequest,
    DailyAttributionCountResponse,
    GeneratedAdLinkCodeResponse,
    UpdateAdLinkRequest,
    UserAdAttributionResponse,
)
from app.modules.advertising.dto import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    AdLinkDto,
    AttributedUserDto,
    CreateAdLinkDto,
    GetAdLinkStatsDto,
    GetAdvertisingSummaryDto,
    ListAdLinkAttributedUsersDto,
    ListAdLinksDto,
    UpdateAdLinkDto,
)
from app.modules.advertising.qr import render_qr_png
from app.modules.advertising.usecases import (
    CreateAdLinkUseCase,
    DeleteAdLinkUseCase,
    GenerateAdLinkCodeUseCase,
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


def _to_response(ad_link: AdLinkDto) -> AdLinkResponse:
    return AdLinkResponse(
        id=ad_link.id,
        name=ad_link.name,
        code=ad_link.code,
        cost=ad_link.cost,
        cost_currency=ad_link.cost_currency,
        is_active=ad_link.is_active,
        allow_bot=ad_link.allow_bot,
        allow_webcabinet=ad_link.allow_webcabinet,
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
    actor: Actor = Depends(require_admin),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> AdLinkPageResponse:
    ad_links, total = await use_case(
        actor, ListAdLinksDto(is_active=is_active, page=page, page_size=page_size)
    )
    return AdLinkPageResponse(items=[_to_response(link) for link in ad_links], total=total)


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
            allow_bot=payload.allow_bot,
            allow_webcabinet=payload.allow_webcabinet,
            note=payload.note,
            created_by=actor.id if actor.id > 0 else None,
        ),
    )
    return _to_response(ad_link)


@router.patch(
    "/links/{ad_link_id}", response_model=AdLinkResponse, responses=error_responses(400, 404)
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
            is_active=payload.is_active,
            allow_bot=payload.allow_bot,
            allow_webcabinet=payload.allow_webcabinet,
            note=payload.note,
        ),
    )
    return _to_response(ad_link)


@router.delete(
    "/links/{ad_link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(400, 404),
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
    "/links/{ad_link_id}/stats", response_model=AdLinkStatsResponse, responses=error_responses(404)
)
@inject
async def get_ad_link_stats(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkStatsUseCase],
    actor: Actor = Depends(require_admin),
    report_currency: Optional[Currency] = Query(None),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
) -> AdLinkStatsResponse:
    stats = await use_case(
        actor,
        GetAdLinkStatsDto(
            ad_link_id=ad_link_id,
            report_currency=report_currency,
            created_from=created_from,
            created_to=created_to,
        ),
    )
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
            DailyAttributionCountResponse(day=row.day, count=row.count, by_channel=row.by_channel)
            for row in stats.daily_registrations
        ],
    )


@router.get(
    "/links/{ad_link_id}/share",
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
    return AdLinkShareUrlsResponse(bot_url=urls.bot_url, webcabinet_url=urls.webcabinet_url)


@router.get("/links/{ad_link_id}/qr", response_class=Response, responses=error_responses(404))
@inject
async def get_ad_link_qr(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkShareUrlsUseCase],
    actor: Actor = Depends(require_admin),
    channel: AdLinkChannel = Query(AdLinkChannel.BOT),
) -> Response:
    urls = await use_case(actor, ad_link_id)
    url = urls.bot_url if channel == AdLinkChannel.BOT else urls.webcabinet_url
    if url is None:
        raise NotFoundError("Channel is unavailable", code=ErrorCode.AD_LINK_CHANNEL_UNAVAILABLE)
    return Response(content=render_qr_png(url), media_type="image/png")


@router.get("/summary", response_model=AdvertisingSummaryResponse)
@inject
async def get_advertising_summary(
    use_case: FromDishka[GetAdvertisingSummaryUseCase],
    actor: Actor = Depends(require_admin),
    is_active: Optional[bool] = Query(None),
    report_currency: Optional[Currency] = Query(None),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
) -> AdvertisingSummaryResponse:
    summary = await use_case(
        actor,
        GetAdvertisingSummaryDto(
            is_active=is_active,
            report_currency=report_currency,
            created_from=created_from,
            created_to=created_to,
        ),
    )
    return AdvertisingSummaryResponse(
        report_currency=summary.report_currency,
        attributions_count=summary.attributions_count,
        attributions_by_channel=summary.attributions_by_channel,
        paid_count=summary.paid_count,
        conversion_rate=summary.conversion_rate,
        revenue=summary.revenue,
        cost=summary.cost,
        cpa=summary.cpa,
        roi=summary.roi,
        links=[
            AdLinkMetricsResponse(
                ad_link_id=link.ad_link_id,
                attributions_count=link.attributions_count,
                paid_count=link.paid_count,
                revenue=link.revenue,
                cost=link.cost,
                roi=link.roi,
            )
            for link in summary.links
        ],
    )


@router.get(
    "/links/{ad_link_id}/users",
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
        items=[_to_attributed_user_response(user) for user in users], total=total
    )


@router.get("/users/{user_id}/attribution", response_model=Optional[UserAdAttributionResponse])
@inject
async def get_user_ad_attribution(
    user_id: int,
    use_case: FromDishka[GetUserAdAttributionUseCase],
    actor: Actor = Depends(require_admin),
) -> Optional[UserAdAttributionResponse]:
    attribution = await use_case(actor, user_id)
    if attribution is None:
        return None
    return UserAdAttributionResponse(**asdict(attribution))


@router.get(
    "/links/{ad_link_id:int}", response_model=AdLinkResponse, responses=error_responses(404)
)
@inject
async def get_ad_link(
    ad_link_id: int,
    use_case: FromDishka[GetAdLinkUseCase],
    actor: Actor = Depends(require_admin),
) -> AdLinkResponse:
    return _to_response(await use_case(actor, ad_link_id))
