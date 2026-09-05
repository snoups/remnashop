from dishka import Provider, Scope, provide

from app.modules.overview.usecases import GetOverviewUseCase


class OverviewProvider(Provider):
    scope = Scope.REQUEST

    get_overview_use_case = provide(GetOverviewUseCase)


def get_overview_providers() -> list[Provider]:
    return [OverviewProvider()]
