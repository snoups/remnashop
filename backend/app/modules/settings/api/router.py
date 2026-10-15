from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Response

from app.api.errors import error_responses
from app.core.enums import AppearanceImageKind
from app.modules.settings.api.schemas import AppearanceResponse
from app.modules.settings.usecases import (
    GetPublicAppearanceImageUseCase,
    GetPublicAppearanceUseCase,
)

router = APIRouter(prefix="/appearance", tags=["appearance"])

# Uploads may be SVG: opened directly, the file must not run scripts or load
# anything, and must never be sniffed into another type.
_IMAGE_HEADERS: Final[dict[str, str]] = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
}


@router.get("", response_model=AppearanceResponse)
@inject
async def get_appearance(use_case: FromDishka[GetPublicAppearanceUseCase]) -> AppearanceResponse:
    settings = await use_case.execute()
    return AppearanceResponse.model_validate(settings, from_attributes=True)


@router.get("/logo", responses=error_responses(404))
@inject
async def get_appearance_logo(use_case: FromDishka[GetPublicAppearanceImageUseCase]) -> Response:
    image = await use_case.execute(AppearanceImageKind.LOGO)
    return Response(content=image.data, media_type=image.content_type, headers=_IMAGE_HEADERS)


@router.get("/favicon", responses=error_responses(404))
@inject
async def get_appearance_favicon(use_case: FromDishka[GetPublicAppearanceImageUseCase]) -> Response:
    image = await use_case.execute(AppearanceImageKind.FAVICON)
    return Response(content=image.data, media_type=image.content_type, headers=_IMAGE_HEADERS)
