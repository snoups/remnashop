from dishka import Provider, Scope, provide, provide_all

from app.modules.analytics.cache import AnalyticsCache
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


class AnalyticsProvider(Provider):
    scope = Scope.REQUEST

    analytics_cache = provide(AnalyticsCache, scope=Scope.APP)
    use_cases = provide_all(
        GetAnalyticsUseCase,
        GetFunnelUseCase,
        GetCohortRetentionUseCase,
        GetLtvBreakdownUseCase,
        GetLtvDistributionUseCase,
        GetPromocodeStatsUseCase,
        GetRetentionUseCase,
        GetRevenueUseCase,
        GetSourcesUseCase,
        GetTrialUseCase,
    )


def get_analytics_providers() -> list[Provider]:
    return [AnalyticsProvider()]
