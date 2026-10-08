from dishka import Provider, Scope, provide_all

from app.modules.access.usecases import CheckRegistrationAccessUseCase


class AccessProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(CheckRegistrationAccessUseCase)


def get_access_providers() -> list[Provider]:
    return [AccessProvider()]
