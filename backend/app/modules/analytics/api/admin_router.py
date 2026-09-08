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
)
from app.modules.analytics.dto import AnalyticsDays, GetAnalyticsDto
from app.modules.analytics.usecases import GetAnalyticsUseCase
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
