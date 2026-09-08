from enum import IntEnum
from typing import cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin
from app.modules.analytics.api.schemas import (
    AnalyticsKpiResponse,
    AnalyticsResponse,
    ChurnSnapshotResponse,
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
from app.modules.users import UserDto

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsPeriodDays(IntEnum):
    # Same FastAPI/Pydantic int-Literal query-param coercion issue as
    # overview/api/admin_router.py's OverviewPeriodDays -- see that file's
    # inline comment for the full explanation.
    ALL = 0
    SEVEN = 7
    THIRTY = 30
    NINETY = 90


@router.get("/overview", response_model=AnalyticsResponse)
@inject
async def get_analytics_overview(
    use_case: FromDishka[GetAnalyticsUseCase],
    actor: UserDto = Depends(require_admin),
    days: AnalyticsPeriodDays = AnalyticsPeriodDays.SEVEN,
) -> AnalyticsResponse:
    analytics = await use_case(actor, GetAnalyticsDto(days=cast(AnalyticsDays, int(days))))
    return AnalyticsResponse(
        days=analytics.days,
        kpi=AnalyticsKpiResponse(
            total_revenue_by_currency=analytics.kpi.total_revenue_by_currency,
            report_currency=analytics.kpi.report_currency,
            mrr=analytics.kpi.mrr,
            arpu=analytics.kpi.arpu,
            active_subscriptions=analytics.kpi.active_subscriptions,
            paid_orders_count=analytics.kpi.paid_orders_count,
            registered_in_period=analytics.kpi.registered_in_period,
            paid_in_period=analytics.kpi.paid_in_period,
            conversion_rate=analytics.kpi.conversion_rate,
        ),
        churn=ChurnSnapshotResponse(
            window_days=analytics.churn.window_days,
            prev_active=analytics.churn.prev_active,
            still_active=analytics.churn.still_active,
            churned=analytics.churn.churned,
            churn_rate=analytics.churn.churn_rate,
            retention_rate=analytics.churn.retention_rate,
        ),
    )


@router.get("/funnel", response_model=FunnelResponse)
@inject
async def get_analytics_funnel(
    use_case: FromDishka[GetFunnelUseCase],
    actor: UserDto = Depends(require_admin),
    days: AnalyticsPeriodDays = AnalyticsPeriodDays.SEVEN,
) -> FunnelResponse:
    funnel = await use_case(actor, GetFunnelDto(days=cast(AnalyticsDays, int(days))))
    return FunnelResponse(
        days=funnel.days,
        steps=[
            FunnelStepResponse(
                key=step.key,
                count=step.count,
                pct_of_start=step.pct_of_start,
                pct_of_prev=step.pct_of_prev,
            )
            for step in funnel.steps
        ],
    )


@router.get("/cohorts", response_model=CohortsResponse)
@inject
async def get_analytics_cohorts(
    use_case: FromDishka[GetCohortRetentionUseCase],
    actor: UserDto = Depends(require_admin),
) -> CohortsResponse:
    cohorts = await use_case(actor)
    return CohortsResponse(
        cohorts=[
            CohortRowResponse(
                cohort=row.cohort,
                cohort_size=row.cohort_size,
                retention_by_month=row.retention_by_month,
            )
            for row in cohorts.cohorts
        ]
    )


@router.get("/ltv-distribution", response_model=LtvDistributionResponse)
@inject
async def get_analytics_ltv_distribution(
    use_case: FromDishka[GetLtvDistributionUseCase],
    actor: UserDto = Depends(require_admin),
) -> LtvDistributionResponse:
    distribution = await use_case(actor)
    return LtvDistributionResponse(
        report_currency=distribution.report_currency,
        buckets=[
            LtvBucketResponse(
                label=bucket.label,
                lower_bound=bucket.lower_bound,
                upper_bound=bucket.upper_bound,
                users=bucket.users,
            )
            for bucket in distribution.buckets
        ],
    )
