from dishka import Provider, Scope, provide

from app.modules.gateways.repository import GatewaysRepository
from app.modules.gateways.usecases import (
    ListGatewaysUseCase,
    ReorderGatewaysUseCase,
    ToggleGatewayActiveUseCase,
    UpdateGatewaySettingsUseCase,
)


class GatewaysProvider(Provider):
    scope = Scope.REQUEST

    gateways_repository = provide(GatewaysRepository)
    list_gateways_use_case = provide(ListGatewaysUseCase)
    update_gateway_settings_use_case = provide(UpdateGatewaySettingsUseCase)
    toggle_gateway_active_use_case = provide(ToggleGatewayActiveUseCase)
    reorder_gateways_use_case = provide(ReorderGatewaysUseCase)


def get_gateways_providers() -> list[Provider]:
    return [GatewaysProvider()]
