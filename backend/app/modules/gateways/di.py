from dishka import Provider, Scope, provide

from app.modules.gateways.repository import GatewaysRepository
from app.modules.gateways.usecases import (
    ListGatewaysUseCase,
    ReorderGatewaysUseCase,
    SetGatewayActiveUseCase,
    UpdateGatewaySettingsUseCase,
)


class GatewaysProvider(Provider):
    scope = Scope.REQUEST

    gateways_repository = provide(GatewaysRepository)
    list_gateways_use_case = provide(ListGatewaysUseCase)
    update_gateway_settings_use_case = provide(UpdateGatewaySettingsUseCase)
    set_gateway_active_use_case = provide(SetGatewayActiveUseCase)
    reorder_gateways_use_case = provide(ReorderGatewaysUseCase)


def get_gateways_providers() -> list[Provider]:
    return [GatewaysProvider()]
