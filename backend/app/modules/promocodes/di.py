from dishka import Provider, Scope, provide

from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases import (
    ActivatePromocodeUseCase,
    CreatePromocodeUseCase,
    DeletePromocodeUseCase,
    GeneratePromocodeCodeUseCase,
    ListPromocodesUseCase,
    UpdatePromocodeUseCase,
)


class PromocodesProvider(Provider):
    scope = Scope.REQUEST

    promocode_repository = provide(PromocodeRepository)
    create_promocode_use_case = provide(CreatePromocodeUseCase)
    update_promocode_use_case = provide(UpdatePromocodeUseCase)
    delete_promocode_use_case = provide(DeletePromocodeUseCase)
    list_promocodes_use_case = provide(ListPromocodesUseCase)
    generate_promocode_code_use_case = provide(GeneratePromocodeCodeUseCase)
    activate_promocode_use_case = provide(ActivatePromocodeUseCase)


def get_promocodes_providers() -> list[Provider]:
    return [PromocodesProvider()]
