from typing import cast

from dishka import Provider, Scope, alias, provide, provide_all

from app.core.ports import LoyaltyThresholdRescaler
from app.modules.loyalty.dispatch import LoyaltyRecalcDispatch
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.tasks import recalculate_loyalty_discounts_task
from app.modules.loyalty.usecases import (
    GetLoyaltySettingsUseCase,
    GetUserLoyaltyUseCase,
    RecalculateLoyaltyDiscountsUseCase,
    SetUserLoyaltyExcludedUseCase,
    UpdateLoyaltySettingsUseCase,
)


class LoyaltyProvider(Provider):
    scope = Scope.REQUEST

    loyalty_repository = provide(LoyaltyRepository)
    loyalty_threshold_rescaler = alias(source=LoyaltyRepository, provides=LoyaltyThresholdRescaler)
    use_cases = provide_all(
        GetLoyaltySettingsUseCase,
        UpdateLoyaltySettingsUseCase,
        RecalculateLoyaltyDiscountsUseCase,
        GetUserLoyaltyUseCase,
        SetUserLoyaltyExcludedUseCase,
    )

    @provide(scope=Scope.APP)
    def recalc_dispatch(self) -> LoyaltyRecalcDispatch:
        return cast(LoyaltyRecalcDispatch, recalculate_loyalty_discounts_task)


def get_loyalty_providers() -> list[Provider]:
    return [LoyaltyProvider()]
