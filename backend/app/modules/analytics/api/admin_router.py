from enum import IntEnum
from typing import cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin
from app.core.actor import Actor
from app.modules.analytics.api.schemas import (
    AnalyticsResponse,
    CohortRowResponse,
    CohortsResponse,
    FunnelResponse,
    FunnelStepResponse,
    LtvBucketResponse,
    LtvDistributionResponse,
)
from app.modules.analytics.dto import AnalyticsDays, GetAnalyticsDto, GetFunnelDto
from app.modules.analytics.usecases import (
    GetAnalyticsUseCase,
    GetCohortRetentionUseCase,
    GetFunnelUseCase,
    GetLtvDistributionUseCase,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsPeriodDays(IntEnum):
    # IntEnum, not Literal[0, 7, 30, 90]: a query string isn't coerced into an
    # int Literal (overview's OverviewPeriodDays does the same)
    ALL = 0
    SEVEN = 7
    THIRTY = 30
    NINETY = 90


@router.get("/overview", response_model=AnalyticsResponse)
@inject
async def get_analytics_overview(
    use_case: FromDishka[GetAnalyticsUseCase],
    actor: Actor = Depends(require_admin),
    days: AnalyticsPeriodDays = AnalyticsPeriodDays.SEVEN,
) -> AnalyticsResponse:
    analytics = await use_case(actor, GetAnalyticsDto(days=cast(AnalyticsDays, int(days))))
    return AnalyticsResponse.model_validate(analytics, from_attributes=True)


@router.get("/funnel", response_model=FunnelResponse)
@inject
async def get_analytics_funnel(
    use_case: FromDishka[GetFunnelUseCase],
    actor: Actor = Depends(require_admin),
    days: AnalyticsPeriodDays = AnalyticsPeriodDays.SEVEN,
) -> FunnelResponse:
    funnel = await use_case(actor, GetFunnelDto(days=cast(AnalyticsDays, int(days))))
    return FunnelResponse(
        days=funnel.days,
        steps=[
            FunnelStepResponse.model_validate(step, from_attributes=True) for step in funnel.steps
        ],
    )


@router.get("/cohorts", response_model=CohortsResponse)
@inject
async def get_analytics_cohorts(
    use_case: FromDishka[GetCohortRetentionUseCase],
    actor: Actor = Depends(require_admin),
) -> CohortsResponse:
    cohorts = await use_case(actor)
    return CohortsResponse(
        cohorts=[
            CohortRowResponse.model_validate(row, from_attributes=True) for row in cohorts.cohorts
        ]
    )


@router.get("/ltv-distribution", response_model=LtvDistributionResponse)
@inject
async def get_analytics_ltv_distribution(
    use_case: FromDishka[GetLtvDistributionUseCase],
    actor: Actor = Depends(require_admin),
) -> LtvDistributionResponse:
    distribution = await use_case(actor)
    return LtvDistributionResponse(
        report_currency=distribution.report_currency,
        buckets=[
            LtvBucketResponse.model_validate(bucket, from_attributes=True)
            for bucket in distribution.buckets
        ],
    )
