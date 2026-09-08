from dishka import Provider, Scope, provide

from app.modules.analytics.usecases import GetAnalyticsUseCase


class AnalyticsProvider(Provider):
    scope = Scope.REQUEST

    get_analytics_use_case = provide(GetAnalyticsUseCase)


def get_analytics_providers() -> list[Provider]:
    return [AnalyticsProvider()]
