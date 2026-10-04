from enum import IntEnum
from typing import cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.core.actor import Actor
from app.modules.overview.api.schemas import (
    AttentionResponse,
    ClientAppsResponse,
    HourlyOnlineResponse,
    NodesOverviewResponse,
    OnlineChartResponse,
    OverviewResponse,
    RegistrationsChartResponse,
    RevenueChartResponse,
)
from app.modules.overview.dto import GetOverviewChartDto, OverviewDays
from app.modules.overview.usecases import (
    GetAttentionUseCase,
    GetClientAppsUseCase,
    GetHourlyOnlineUseCase,
    GetNodesOverviewUseCase,
    GetOnlineChartUseCase,
    GetOverviewUseCase,
    GetRegistrationsChartUseCase,
    GetRevenueChartUseCase,
)

router = APIRouter(prefix="/overview", tags=["overview"])


class OverviewPeriodDays(IntEnum):
    # a query string isn't coerced into Literal[7, 30, 90] (`?days=7` 422s), an
    # IntEnum is; mapped back to OverviewDays when building GetOverviewChartDto
    ALL = 0
    SEVEN = 7
    THIRTY = 30
    NINETY = 90


def _chart_dto(days: OverviewPeriodDays) -> GetOverviewChartDto:
    return GetOverviewChartDto(days=cast(OverviewDays, int(days)))


@router.get("", response_model=OverviewResponse)
@inject
async def get_overview(
    use_case: FromDishka[GetOverviewUseCase],
    actor: Actor = Depends(require_admin_user),
) -> OverviewResponse:
    overview = await use_case(actor)
    return OverviewResponse.model_validate(overview, from_attributes=True)


@router.get("/revenue", response_model=RevenueChartResponse)
@inject
async def get_overview_revenue(
    use_case: FromDishka[GetRevenueChartUseCase],
    actor: Actor = Depends(require_admin_user),
    days: OverviewPeriodDays = OverviewPeriodDays.SEVEN,
) -> RevenueChartResponse:
    chart = await use_case(actor, _chart_dto(days))
    return RevenueChartResponse.model_validate(chart, from_attributes=True)


@router.get("/registrations", response_model=RegistrationsChartResponse)
@inject
async def get_overview_registrations(
    use_case: FromDishka[GetRegistrationsChartUseCase],
    actor: Actor = Depends(require_admin_user),
    days: OverviewPeriodDays = OverviewPeriodDays.SEVEN,
) -> RegistrationsChartResponse:
    chart = await use_case(actor, _chart_dto(days))
    return RegistrationsChartResponse.model_validate(chart, from_attributes=True)


@router.get("/online", response_model=OnlineChartResponse)
@inject
async def get_overview_online(
    use_case: FromDishka[GetOnlineChartUseCase],
    actor: Actor = Depends(require_admin_user),
    days: OverviewPeriodDays = OverviewPeriodDays.SEVEN,
) -> OnlineChartResponse:
    chart = await use_case(actor, _chart_dto(days))
    return OnlineChartResponse.model_validate(chart, from_attributes=True)


@router.get("/online/hourly", response_model=HourlyOnlineResponse)
@inject
async def get_overview_online_hourly(
    use_case: FromDishka[GetHourlyOnlineUseCase],
    actor: Actor = Depends(require_admin_user),
) -> HourlyOnlineResponse:
    chart = await use_case(actor)
    return HourlyOnlineResponse.model_validate(chart, from_attributes=True)


@router.get("/nodes", response_model=NodesOverviewResponse)
@inject
async def get_overview_nodes(
    use_case: FromDishka[GetNodesOverviewUseCase],
    actor: Actor = Depends(require_admin_user),
) -> NodesOverviewResponse:
    nodes = await use_case(actor)
    return NodesOverviewResponse.model_validate(nodes, from_attributes=True)


@router.get("/client-apps", response_model=ClientAppsResponse)
@inject
async def get_overview_client_apps(
    use_case: FromDishka[GetClientAppsUseCase],
    actor: Actor = Depends(require_admin_user),
) -> ClientAppsResponse:
    apps = await use_case(actor)
    return ClientAppsResponse.model_validate(apps, from_attributes=True)


@router.get("/attention", response_model=AttentionResponse)
@inject
async def get_overview_attention(
    use_case: FromDishka[GetAttentionUseCase],
    actor: Actor = Depends(require_admin_user),
) -> AttentionResponse:
    attention = await use_case(actor)
    return AttentionResponse.model_validate(attention, from_attributes=True)
