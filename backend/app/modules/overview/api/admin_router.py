from enum import IntEnum
from typing import cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin
from app.core.actor import Actor
from app.modules.overview.api.schemas import (
    OnlineChartResponse,
    OverviewResponse,
    RegistrationsChartResponse,
    RevenueChartResponse,
)
from app.modules.overview.dto import GetOverviewChartDto, OverviewDays
from app.modules.overview.usecases import (
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
    actor: Actor = Depends(require_admin),
) -> OverviewResponse:
    overview = await use_case(actor)
    return OverviewResponse.model_validate(overview, from_attributes=True)


@router.get("/revenue", response_model=RevenueChartResponse)
@inject
async def get_overview_revenue(
    use_case: FromDishka[GetRevenueChartUseCase],
    actor: Actor = Depends(require_admin),
    days: OverviewPeriodDays = OverviewPeriodDays.SEVEN,
) -> RevenueChartResponse:
    chart = await use_case(actor, _chart_dto(days))
    return RevenueChartResponse.model_validate(chart, from_attributes=True)


@router.get("/registrations", response_model=RegistrationsChartResponse)
@inject
async def get_overview_registrations(
    use_case: FromDishka[GetRegistrationsChartUseCase],
    actor: Actor = Depends(require_admin),
    days: OverviewPeriodDays = OverviewPeriodDays.SEVEN,
) -> RegistrationsChartResponse:
    chart = await use_case(actor, _chart_dto(days))
    return RegistrationsChartResponse.model_validate(chart, from_attributes=True)


@router.get("/online", response_model=OnlineChartResponse)
@inject
async def get_overview_online(
    use_case: FromDishka[GetOnlineChartUseCase],
    actor: Actor = Depends(require_admin),
    days: OverviewPeriodDays = OverviewPeriodDays.SEVEN,
) -> OnlineChartResponse:
    chart = await use_case(actor, _chart_dto(days))
    return OnlineChartResponse.model_validate(chart, from_attributes=True)
