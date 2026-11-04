from dishka import Provider, Scope, provide_all

from app.modules.overview.usecases import (
    GetAttentionUseCase,
    GetClientAppsUseCase,
    GetHourlyOnlineUseCase,
    GetNodesOverviewUseCase,
    GetOnlineChartUseCase,
    GetOverviewUseCase,
    GetRecapUseCase,
    GetRevenueChartUseCase,
    SampleRemnawaveOnlineUseCase,
)


class OverviewProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        GetOverviewUseCase,
        GetRecapUseCase,
        GetAttentionUseCase,
        GetNodesOverviewUseCase,
        GetClientAppsUseCase,
        GetRevenueChartUseCase,
        GetOnlineChartUseCase,
        GetHourlyOnlineUseCase,
        SampleRemnawaveOnlineUseCase,
    )


def get_overview_providers() -> list[Provider]:
    return [OverviewProvider()]
