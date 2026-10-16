from dishka import Provider, Scope, provide_all

from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.repository import PlanRepository
from app.modules.plans.usecases import (
    AdjustBasePricesUseCase,
    CreateAddOnUseCase,
    CreatePlanUseCase,
    DeleteAddOnUseCase,
    DeletePlanUseCase,
    GetAddOnUseCase,
    GetPlanShareUrlsUseCase,
    GetPlanUseCase,
    GetPriceBookUseCase,
    ListAddOnsUseCase,
    ListPlansUseCase,
    PreviewPricingChangeUseCase,
    ReorderPlansUseCase,
    SetAddOnBasePriceUseCase,
    SetAddOnPriceOverrideUseCase,
    SetPlanDurationBasePriceUseCase,
    SetPlanDurationsUseCase,
    SetPlanPriceOverrideUseCase,
    SwitchAnchorCurrencyUseCase,
    UpdateAddOnUseCase,
    UpdatePlanAccessUseCase,
    UpdatePlanDiscountUseCase,
    UpdatePlanSquadsUseCase,
    UpdatePlanUseCase,
)


class PlansProvider(Provider):
    scope = Scope.REQUEST

    repositories = provide_all(
        PlanRepository,
        AddOnRepository,
    )
    use_cases = provide_all(
        ListPlansUseCase,
        GetPlanUseCase,
        GetPlanShareUrlsUseCase,
        CreatePlanUseCase,
        UpdatePlanUseCase,
        DeletePlanUseCase,
        SetPlanDurationsUseCase,
        SetPlanDurationBasePriceUseCase,
        SetPlanPriceOverrideUseCase,
        UpdatePlanAccessUseCase,
        UpdatePlanSquadsUseCase,
        UpdatePlanDiscountUseCase,
        ReorderPlansUseCase,
        CreateAddOnUseCase,
        DeleteAddOnUseCase,
        GetAddOnUseCase,
        ListAddOnsUseCase,
        SetAddOnBasePriceUseCase,
        SetAddOnPriceOverrideUseCase,
        UpdateAddOnUseCase,
        AdjustBasePricesUseCase,
        GetPriceBookUseCase,
        PreviewPricingChangeUseCase,
        SwitchAnchorCurrencyUseCase,
    )


def get_plans_providers() -> list[Provider]:
    return [PlansProvider()]
