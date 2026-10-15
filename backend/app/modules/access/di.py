from dishka import Provider, Scope, provide

from app.modules.access.usecases import CheckRegistrationAccessUseCase


class AccessProvider(Provider):
    scope = Scope.REQUEST

    check_registration_access_use_case = provide(CheckRegistrationAccessUseCase)


def get_access_providers() -> list[Provider]:
    return [AccessProvider()]
