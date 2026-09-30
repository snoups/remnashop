from dishka import Provider, Scope, provide

from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases import (
    ActivatePromocodeUseCase,
    CreatePromocodeUseCase,
    DeletePromocodeUseCase,
    GeneratePromocodeCodeUseCase,
    GetPromocodeSummaryUseCase,
    ListPromocodeActivatedUsersUseCase,
    ListPromocodesUseCase,
    ListUserPromocodeActivationsUseCase,
    UpdatePromocodeUseCase,
    ValidatePromocodeUseCase,
)


class PromocodesProvider(Provider):
    scope = Scope.REQUEST

    promocode_repository = provide(PromocodeRepository)
    create_promocode_use_case = provide(CreatePromocodeUseCase)
    update_promocode_use_case = provide(UpdatePromocodeUseCase)
    delete_promocode_use_case = provide(DeletePromocodeUseCase)
    list_promocodes_use_case = provide(ListPromocodesUseCase)
    list_user_promocode_activations_use_case = provide(ListUserPromocodeActivationsUseCase)
    generate_promocode_code_use_case = provide(GeneratePromocodeCodeUseCase)
    get_promocode_summary_use_case = provide(GetPromocodeSummaryUseCase)
    list_promocode_activated_users_use_case = provide(ListPromocodeActivatedUsersUseCase)
    activate_promocode_use_case = provide(ActivatePromocodeUseCase)
    validate_promocode_use_case = provide(ValidatePromocodeUseCase)


def get_promocodes_providers() -> list[Provider]:
    return [PromocodesProvider()]
