from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response

from app.api.dependencies.public import get_current_user
from app.api.errors import error_responses
from app.core.enums import AppearanceImageKind, AppearanceTarget
from app.modules.settings.api.schemas import AppearanceResponse, CabinetSettingsResponse
from app.modules.settings.usecases import (
    GetCabinetSettingsUseCase,
    GetPublicAppearanceImageUseCase,
    GetPublicAppearanceUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/appearance", tags=["appearance"])

# Uploads may be SVG: opened directly, the file must not run scripts or load
# anything, and must never be sniffed into another type.
_IMAGE_HEADERS: Final[dict[str, str]] = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
}


@router.get("/{target}", response_model=AppearanceResponse)
@inject
async def get_appearance(
    target: AppearanceTarget, use_case: FromDishka[GetPublicAppearanceUseCase]
) -> AppearanceResponse:
    settings = await use_case.execute(target)
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.get("/{target}/logo", responses=error_responses(404))
@inject
async def get_appearance_logo(
    target: AppearanceTarget, use_case: FromDishka[GetPublicAppearanceImageUseCase]
) -> Response:
    image = await use_case.execute(target, AppearanceImageKind.LOGO)
    return Response(content=image.data, media_type=image.content_type, headers=_IMAGE_HEADERS)


@router.get("/{target}/favicon", responses=error_responses(404))
@inject
async def get_appearance_favicon(
    target: AppearanceTarget, use_case: FromDishka[GetPublicAppearanceImageUseCase]
) -> Response:
    image = await use_case.execute(target, AppearanceImageKind.FAVICON)
    return Response(content=image.data, media_type=image.content_type, headers=_IMAGE_HEADERS)


shop_router = APIRouter(prefix="/shop", tags=["shop"])


@shop_router.get("/public-settings", response_model=CabinetSettingsResponse)
@inject
async def get_public_shop_settings(
    use_case: FromDishka[GetCabinetSettingsUseCase],
    actor: UserDto = Depends(get_current_user),
) -> CabinetSettingsResponse:
    return CabinetSettingsResponse.model_validate(await use_case(actor), from_attributes=True)
