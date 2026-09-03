from dishka import Provider, Scope, provide

from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.usecases import (
    AdjustBasePricesUseCase,
    GetPriceBookUseCase,
    PreviewPricingChangeUseCase,
    SwitchAnchorCurrencyUseCase,
    UpdateCurrencyRateUseCase,
    UpdatePricingSettingsUseCase,
)


class PricingProvider(Provider):
    scope = Scope.REQUEST

    pricing_repository = provide(PricingRepository)
    get_price_book_use_case = provide(GetPriceBookUseCase)
    update_currency_rate_use_case = provide(UpdateCurrencyRateUseCase)
    update_pricing_settings_use_case = provide(UpdatePricingSettingsUseCase)
    switch_anchor_currency_use_case = provide(SwitchAnchorCurrencyUseCase)
    preview_pricing_change_use_case = provide(PreviewPricingChangeUseCase)
    adjust_base_prices_use_case = provide(AdjustBasePricesUseCase)


def get_pricing_providers() -> list[Provider]:
    return [PricingProvider()]
