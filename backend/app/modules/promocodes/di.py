from dishka import Provider, Scope, provide, provide_all

from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases import (
    ActivatePromocodeUseCase,
    CreatePromocodeUseCase,
    DeletePromocodeUseCase,
    GeneratePromocodeCodeUseCase,
    GetPromocodeSummaryUseCase,
    GetPromocodeUseCase,
    ListPromocodeActivatedUsersUseCase,
    ListPromocodesUseCase,
    ListUserPromocodeActivationsUseCase,
    UpdatePromocodeUseCase,
    ValidatePromocodeUseCase,
)


class PromocodesProvider(Provider):
    scope = Scope.REQUEST

    promocode_repository = provide(PromocodeRepository)
    use_cases = provide_all(
        CreatePromocodeUseCase,
        UpdatePromocodeUseCase,
        DeletePromocodeUseCase,
        ListPromocodesUseCase,
        GetPromocodeUseCase,
        ListUserPromocodeActivationsUseCase,
        GeneratePromocodeCodeUseCase,
        GetPromocodeSummaryUseCase,
        ListPromocodeActivatedUsersUseCase,
        ActivatePromocodeUseCase,
        ValidatePromocodeUseCase,
    )


def get_promocodes_providers() -> list[Provider]:
    return [PromocodesProvider()]
