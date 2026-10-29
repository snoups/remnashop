from dishka import Provider, Scope, provide, provide_all

from app.modules.connect_guide.repository import ConnectGuideRepository
from app.modules.connect_guide.usecases import (
    GetConnectGuideUseCase,
    GetPublicConnectGuideUseCase,
    ResetConnectGuideUseCase,
    UpdateConnectGuideUseCase,
)


class ConnectGuideProvider(Provider):
    scope = Scope.REQUEST

    connect_guide_repository = provide(ConnectGuideRepository)
    use_cases = provide_all(
        GetConnectGuideUseCase,
        GetPublicConnectGuideUseCase,
        UpdateConnectGuideUseCase,
        ResetConnectGuideUseCase,
    )


def get_connect_guide_providers() -> list[Provider]:
    return [ConnectGuideProvider()]
