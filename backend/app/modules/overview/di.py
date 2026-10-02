from dishka import Provider, Scope, provide_all

from app.modules.overview.usecases import GetOverviewUseCase, SampleRemnawaveOnlineUseCase


class OverviewProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        GetOverviewUseCase,
        SampleRemnawaveOnlineUseCase,
    )


def get_overview_providers() -> list[Provider]:
    return [OverviewProvider()]
