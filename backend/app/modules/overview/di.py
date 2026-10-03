from dishka import Provider, Scope, provide_all

from app.modules.overview.usecases import (
    GetOnlineChartUseCase,
    GetOverviewUseCase,
    GetRegistrationsChartUseCase,
    GetRevenueChartUseCase,
    SampleRemnawaveOnlineUseCase,
)


class OverviewProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        GetOverviewUseCase,
        GetRevenueChartUseCase,
        GetRegistrationsChartUseCase,
        GetOnlineChartUseCase,
        SampleRemnawaveOnlineUseCase,
    )


def get_overview_providers() -> list[Provider]:
    return [OverviewProvider()]
