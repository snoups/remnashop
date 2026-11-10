from dishka import Provider, Scope, alias, provide, provide_all

from app.modules.plans import PlanReferenceCleaner
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.targets import PromocodeTargets
from app.modules.promocodes.usecases import (
    ActivatePromocodeUseCase,
    CreatePromocodeUseCase,
    DeletePromocodeUseCase,
    GeneratePromocodeCodeUseCase,
    GetPromocodeRewardUseCase,
    GetPromocodeSummaryUseCase,
    GetPromocodeUseCase,
    ListPromocodeActivatedUsersUseCase,
    ListPromocodesUseCase,
    ListPromocodeTargetsUseCase,
    ListUserPromocodeActivationsUseCase,
    UpdatePromocodeUseCase,
    ValidatePromocodeUseCase,
    WarnExpiringPromocodeDiscountsUseCase,
)
from app.modules.transactions import PromocodeLiveness
from app.modules.users import PromocodeLiveness as UserPromocodeLiveness


class PromocodesProvider(Provider):
    scope = Scope.REQUEST

    promocode_repository = provide(PromocodeRepository)
    promocode_targets = provide(PromocodeTargets)
    promocode_liveness = alias(source=PromocodeRepository, provides=PromocodeLiveness)
    user_promocode_liveness = alias(source=PromocodeRepository, provides=UserPromocodeLiveness)
    plan_reference_cleaner = alias(source=PromocodeRepository, provides=PlanReferenceCleaner)
    use_cases = provide_all(
        CreatePromocodeUseCase,
        UpdatePromocodeUseCase,
        DeletePromocodeUseCase,
        ListPromocodesUseCase,
        GetPromocodeUseCase,
        GetPromocodeRewardUseCase,
        ListUserPromocodeActivationsUseCase,
        GeneratePromocodeCodeUseCase,
        GetPromocodeSummaryUseCase,
        ListPromocodeActivatedUsersUseCase,
        ActivatePromocodeUseCase,
        ListPromocodeTargetsUseCase,
        ValidatePromocodeUseCase,
        WarnExpiringPromocodeDiscountsUseCase,
    )


def get_promocodes_providers() -> list[Provider]:
    return [PromocodesProvider()]
