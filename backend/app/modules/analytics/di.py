from dishka import Provider, Scope, provide

from app.modules.analytics.usecases import (
    GetAnalyticsUseCase,
    GetCohortRetentionUseCase,
    GetFunnelUseCase,
    GetLtvDistributionUseCase,
)


class AnalyticsProvider(Provider):
    scope = Scope.REQUEST

    get_analytics_use_case = provide(GetAnalyticsUseCase)
    get_funnel_use_case = provide(GetFunnelUseCase)
    get_cohort_retention_use_case = provide(GetCohortRetentionUseCase)
    get_ltv_distribution_use_case = provide(GetLtvDistributionUseCase)


def get_analytics_providers() -> list[Provider]:
    return [AnalyticsProvider()]
