from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import Locale
from app.modules.banners.api.schemas import BannerMetaResponse
from app.modules.banners.dto import BannerKeyDto, UploadBannerFileDto
from app.modules.banners.usecases import (
    DeleteBannerUseCase,
    GetBannerImageUseCase,
    RestoreDefaultBannerUseCase,
    UploadBannerUseCase,
)
from app.modules.banners.usecases.upload_banner import MAX_BANNER_SIZE_BYTES

router = APIRouter(prefix="/banners", tags=["banners"])


@router.put("/{name}/{locale}", response_model=BannerMetaResponse, responses=error_responses(400))
@inject
async def upload_banner(
    name: str,
    locale: Locale,
    use_case: FromDishka[UploadBannerUseCase],
    file: UploadFile = File(...),
    actor: Actor = Depends(require_admin),
) -> BannerMetaResponse:
    # bounded read: an oversized upload is rejected before it's buffered
    data = await file.read(MAX_BANNER_SIZE_BYTES + 1)
    banner = await use_case(
        actor,
        UploadBannerFileDto(
            name=name, locale=locale, content_type=file.content_type or "", data=data
        ),
    )
    return BannerMetaResponse.model_validate(banner, from_attributes=True)


@router.delete(
    "/{name}/{locale}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def delete_banner(
    name: str,
    locale: Locale,
    use_case: FromDishka[DeleteBannerUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, BannerKeyDto(name=name, locale=locale))


@router.get("/{name}/{locale}/image", responses=error_responses(404))
@inject
async def get_banner_image(
    name: str,
    locale: Locale,
    use_case: FromDishka[GetBannerImageUseCase],
    actor: Actor = Depends(require_admin),
) -> Response:
    data, content_type = await use_case(actor, BannerKeyDto(name=name, locale=locale))
    return Response(content=data, media_type=content_type)


@router.post("/actions/reset-default", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def reset_default_banner(
    use_case: FromDishka[RestoreDefaultBannerUseCase],
    actor: Actor = Depends(require_admin),
) -> Response:
    await use_case(actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
