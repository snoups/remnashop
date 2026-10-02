from dishka import Provider, Scope, provide, provide_all

from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.usecases import UpdateCurrencyRateUseCase, UpdatePricingSettingsUseCase


class PricingProvider(Provider):
    scope = Scope.REQUEST

    pricing_repository = provide(PricingRepository)
    use_cases = provide_all(
        UpdateCurrencyRateUseCase,
        UpdatePricingSettingsUseCase,
    )


def get_pricing_providers() -> list[Provider]:
    return [PricingProvider()]
