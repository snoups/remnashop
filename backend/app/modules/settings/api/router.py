from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Response, status

from app.core.enums import AppearanceImageKind
from app.core.exceptions import NotFoundError
from app.modules.settings.api.schemas import AppearanceResponse
from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.usecases import (
    GetPublicAppearanceImageUseCase,
    GetPublicAppearanceUseCase,
)

router = APIRouter(prefix="/appearance", tags=["appearance"])


def _to_appearance_response(settings: AppearanceSettingsDto) -> AppearanceResponse:
    return AppearanceResponse(
        brand_name=settings.brand_name,
        primary_color=settings.primary_color,
        shader_palette=settings.shader_palette,
        shader_enabled=settings.shader_enabled,
        has_logo=settings.has_logo,
        has_favicon=settings.has_favicon,
    )


@router.get("", response_model=AppearanceResponse)
@inject
async def get_appearance(use_case: FromDishka[GetPublicAppearanceUseCase]) -> AppearanceResponse:
    settings = await use_case.execute()
    return _to_appearance_response(settings)


@router.get("/logo")
@inject
async def get_appearance_logo(use_case: FromDishka[GetPublicAppearanceImageUseCase]) -> Response:
    try:
        data, content_type = await use_case.execute(AppearanceImageKind.LOGO)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(content=data, media_type=content_type)


@router.get("/favicon")
@inject
async def get_appearance_favicon(use_case: FromDishka[GetPublicAppearanceImageUseCase]) -> Response:
    try:
        data, content_type = await use_case.execute(AppearanceImageKind.FAVICON)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(content=data, media_type=content_type)
