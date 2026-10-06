from dishka import Provider, Scope, alias, provide, provide_all

from app.core.ports import PlanReferenceCleaner, PromocodeLiveness
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
    promocode_liveness = alias(source=PromocodeRepository, provides=PromocodeLiveness)
    plan_reference_cleaner = alias(source=PromocodeRepository, provides=PlanReferenceCleaner)
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
