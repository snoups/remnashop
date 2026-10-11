from datetime import datetime
from typing import Literal, Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.modules.analytics.api.schemas import (
    AnalyticsResponse,
    CohortRowResponse,
    CohortsResponse,
    FunnelResponse,
    LtvBreakdownResponse,
    LtvBucketResponse,
    LtvDistributionResponse,
    PromocodeStatsResponse,
    RetentionResponse,
    RevenueResponse,
    SourcesResponse,
    TrialResponse,
)
from app.modules.analytics.dto import AnalyticsPeriodQueryDto, GetRevenueDto
from app.modules.analytics.usecases import (
    GetAnalyticsUseCase,
    GetCohortRetentionUseCase,
    GetFunnelUseCase,
    GetLtvBreakdownUseCase,
    GetLtvDistributionUseCase,
    GetPromocodeStatsUseCase,
    GetRetentionUseCase,
    GetRevenueUseCase,
    GetSourcesUseCase,
    GetTrialUseCase,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _period_query(
    period_from: Optional[datetime] = None, period_to: Optional[datetime] = None
) -> AnalyticsPeriodQueryDto:
    return AnalyticsPeriodQueryDto(period_from=period_from, period_to=period_to)


@router.get("/overview", response_model=AnalyticsResponse, responses=error_responses(400))
@inject
async def get_analytics_overview(
    use_case: FromDishka[GetAnalyticsUseCase],
    actor: Actor = Depends(require_admin),
    query: AnalyticsPeriodQueryDto = Depends(_period_query),
) -> AnalyticsResponse:
    return AnalyticsResponse.model_validate(await use_case(actor, query), from_attributes=True)


@router.get("/funnel", response_model=FunnelResponse, responses=error_responses(400))
@inject
async def get_analytics_funnel(
    use_case: FromDishka[GetFunnelUseCase],
    actor: Actor = Depends(require_admin),
    query: AnalyticsPeriodQueryDto = Depends(_period_query),
) -> FunnelResponse:
    return FunnelResponse.model_validate(await use_case(actor, query), from_attributes=True)


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
        payers=distribution.payers,
        mean=distribution.mean,
        median=distribution.median,
    )


@router.get("/ltv-breakdown", response_model=LtvBreakdownResponse, responses=error_responses())
@inject
async def get_analytics_ltv_breakdown(
    use_case: FromDishka[GetLtvBreakdownUseCase],
    actor: Actor = Depends(require_admin),
) -> LtvBreakdownResponse:
    return LtvBreakdownResponse.model_validate(await use_case(actor), from_attributes=True)


@router.get("/revenue", response_model=RevenueResponse, responses=error_responses(400))
@inject
async def get_analytics_revenue(
    use_case: FromDishka[GetRevenueUseCase],
    actor: Actor = Depends(require_admin),
    query: AnalyticsPeriodQueryDto = Depends(_period_query),
    granularity: Literal["day", "week", "month"] = "day",
) -> RevenueResponse:
    revenue = await use_case(
        actor,
        GetRevenueDto(
            period_from=query.period_from, period_to=query.period_to, granularity=granularity
        ),
    )
    return RevenueResponse.model_validate(revenue, from_attributes=True)


@router.get("/trial", response_model=TrialResponse, responses=error_responses(400))
@inject
async def get_analytics_trial(
    use_case: FromDishka[GetTrialUseCase],
    actor: Actor = Depends(require_admin),
    query: AnalyticsPeriodQueryDto = Depends(_period_query),
) -> TrialResponse:
    return TrialResponse.model_validate(await use_case(actor, query), from_attributes=True)


@router.get("/retention", response_model=RetentionResponse, responses=error_responses())
@inject
async def get_analytics_retention(
    use_case: FromDishka[GetRetentionUseCase],
    actor: Actor = Depends(require_admin),
) -> RetentionResponse:
    return RetentionResponse.model_validate(await use_case(actor), from_attributes=True)


@router.get("/sources", response_model=SourcesResponse, responses=error_responses(400))
@inject
async def get_analytics_sources(
    use_case: FromDishka[GetSourcesUseCase],
    actor: Actor = Depends(require_admin),
    query: AnalyticsPeriodQueryDto = Depends(_period_query),
) -> SourcesResponse:
    return SourcesResponse.model_validate(await use_case(actor, query), from_attributes=True)


@router.get("/promocodes", response_model=PromocodeStatsResponse, responses=error_responses(400))
@inject
async def get_analytics_promocodes(
    use_case: FromDishka[GetPromocodeStatsUseCase],
    actor: Actor = Depends(require_admin),
    query: AnalyticsPeriodQueryDto = Depends(_period_query),
) -> PromocodeStatsResponse:
    return PromocodeStatsResponse.model_validate(await use_case(actor, query), from_attributes=True)
