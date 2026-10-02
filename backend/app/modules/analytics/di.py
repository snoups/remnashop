from dishka import Provider, Scope, provide_all

from app.modules.analytics.usecases import (
    GetAnalyticsUseCase,
    GetCohortRetentionUseCase,
    GetFunnelUseCase,
    GetLtvDistributionUseCase,
)


class AnalyticsProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        GetAnalyticsUseCase,
        GetFunnelUseCase,
        GetCohortRetentionUseCase,
        GetLtvDistributionUseCase,
    )


def get_analytics_providers() -> list[Provider]:
    return [AnalyticsProvider()]
