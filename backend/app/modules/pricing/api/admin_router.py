from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.admin import require_admin
from app.core.enums import Currency
from app.core.exceptions import ValidationError
from app.modules.pricing.api.schemas import (
    AdjustBasePricesRequest,
    PreviewPricingChangeRequest,
    PriceBookResponse,
    PricingDiffResponse,
    PricingSettingsResponse,
    SwitchAnchorRequest,
    UpdateCurrencyRateRequest,
    UpdatePricingSettingsRequest,
    to_diff_response,
    to_price_book_response,
)
from app.modules.pricing.dto import (
    AdjustBasePricesDto,
    PricingChangePreviewDto,
    SwitchAnchorCurrencyDto,
    UpdateCurrencyRateDto,
    UpdatePricingSettingsDto,
)
from app.modules.pricing.usecases import (
    AdjustBasePricesUseCase,
    GetPriceBookUseCase,
    PreviewPricingChangeUseCase,
    SwitchAnchorCurrencyUseCase,
    UpdateCurrencyRateUseCase,
    UpdatePricingSettingsUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/book", response_model=PriceBookResponse)
@inject
async def get_price_book(
    use_case: FromDishka[GetPriceBookUseCase],
    actor: UserDto = Depends(require_admin),
) -> PriceBookResponse:
    book = await use_case(actor)
    return to_price_book_response(book)


@router.put("/rates/{currency}", response_model=PriceBookResponse)
@inject
async def update_currency_rate(
    currency: Currency,
    payload: UpdateCurrencyRateRequest,
    use_case: FromDishka[UpdateCurrencyRateUseCase],
    price_book_use_case: FromDishka[GetPriceBookUseCase],
    actor: UserDto = Depends(require_admin),
) -> PriceBookResponse:
    try:
        await use_case(
            actor,
            UpdateCurrencyRateDto(
                currency=currency,
                rate=payload.rate,
                rounding_mode=payload.rounding_mode,
                charm_ending=payload.charm_ending,
                min_amount=payload.min_amount,
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    book = await price_book_use_case(actor)
    return to_price_book_response(book)


@router.put("/settings", response_model=PricingSettingsResponse)
@inject
async def update_pricing_settings(
    payload: UpdatePricingSettingsRequest,
    use_case: FromDishka[UpdatePricingSettingsUseCase],
    actor: UserDto = Depends(require_admin),
) -> PricingSettingsResponse:
    settings = await use_case(
        actor,
        UpdatePricingSettingsDto(
            price_per_day=payload.price_per_day, price_per_gb=payload.price_per_gb
        ),
    )
    return PricingSettingsResponse(
        anchor_currency=settings.anchor_currency,
        price_per_day=settings.price_per_day,
        price_per_gb=settings.price_per_gb,
    )


@router.post("/anchor", response_model=PriceBookResponse)
@inject
async def switch_anchor_currency(
    payload: SwitchAnchorRequest,
    use_case: FromDishka[SwitchAnchorCurrencyUseCase],
    actor: UserDto = Depends(require_admin),
) -> PriceBookResponse:
    try:
        book = await use_case(actor, SwitchAnchorCurrencyDto(new_anchor=payload.new_anchor))
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return to_price_book_response(book)


@router.post("/preview", response_model=PricingDiffResponse)
@inject
async def preview_pricing_change(
    payload: PreviewPricingChangeRequest,
    use_case: FromDishka[PreviewPricingChangeUseCase],
    actor: UserDto = Depends(require_admin),
) -> PricingDiffResponse:
    rate = None
    if payload.rate is not None:
        rate = UpdateCurrencyRateDto(
            currency=payload.rate.currency,
            rate=payload.rate.rate,
            rounding_mode=payload.rate.rounding_mode,
            charm_ending=payload.rate.charm_ending,
            min_amount=payload.rate.min_amount,
        )
    adjust = None
    if payload.adjust is not None:
        adjust = AdjustBasePricesDto(
            scope=payload.adjust.scope,
            factor=payload.adjust.factor,
            plan_duration_ids=payload.adjust.plan_duration_ids,
            addon_ids=payload.adjust.addon_ids,
        )
    try:
        diff = await use_case(
            actor, PricingChangePreviewDto(rate=rate, anchor=payload.anchor, adjust=adjust)
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return to_diff_response(diff)


@router.post("/base/adjust", response_model=PriceBookResponse)
@inject
async def adjust_base_prices(
    payload: AdjustBasePricesRequest,
    use_case: FromDishka[AdjustBasePricesUseCase],
    actor: UserDto = Depends(require_admin),
) -> PriceBookResponse:
    book = await use_case(
        actor,
        AdjustBasePricesDto(
            scope=payload.scope,
            factor=payload.factor,
            plan_duration_ids=payload.plan_duration_ids,
            addon_ids=payload.addon_ids,
        ),
    )
    return to_price_book_response(book)
