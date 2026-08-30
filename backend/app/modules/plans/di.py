from dishka import Provider, Scope, provide

from app.modules.plans.repository import PlanRepository
from app.modules.plans.usecases import (
    CreatePlanUseCase,
    DeletePlanUseCase,
    ListActivePlansUseCase,
    ListPlansUseCase,
    ReorderPlansUseCase,
    SetPlanDurationsUseCase,
    UpdatePlanAccessUseCase,
    UpdatePlanSquadsUseCase,
    UpdatePlanUseCase,
)


class PlansProvider(Provider):
    scope = Scope.REQUEST

    plan_repository = provide(PlanRepository)
    list_plans_use_case = provide(ListPlansUseCase)
    list_active_plans_use_case = provide(ListActivePlansUseCase)
    create_plan_use_case = provide(CreatePlanUseCase)
    update_plan_use_case = provide(UpdatePlanUseCase)
    delete_plan_use_case = provide(DeletePlanUseCase)
    set_plan_durations_use_case = provide(SetPlanDurationsUseCase)
    update_plan_access_use_case = provide(UpdatePlanAccessUseCase)
    update_plan_squads_use_case = provide(UpdatePlanSquadsUseCase)
    reorder_plans_use_case = provide(ReorderPlansUseCase)


def get_plans_providers() -> list[Provider]:
    return [PlansProvider()]
