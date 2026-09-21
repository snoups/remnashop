from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.api.dependencies.admin import require_admin
from app.core.enums import Locale
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.banners.api.schemas import BannerListResponse, BannerMetaResponse
from app.modules.banners.dto import BannerDto, BannerKeyDto
from app.modules.banners.usecases import (
    DeleteBannerUseCase,
    GetBannerImageUseCase,
    ListBannersUseCase,
    RestoreDefaultBannerUseCase,
    UploadBannerInput,
    UploadBannerUseCase,
)
from app.modules.banners.usecases.upload_banner import MAX_BANNER_SIZE_BYTES
from app.modules.users import UserDto

router = APIRouter(prefix="/banners", tags=["banners"])


def _to_meta_response(banner: BannerDto) -> BannerMetaResponse:
    return BannerMetaResponse(
        name=banner.name,
        locale=banner.locale,
        content_type=banner.content_type,
        size_bytes=banner.size_bytes,
    )


@router.get("", response_model=BannerListResponse)
@inject
async def list_banners(
    use_case: FromDishka[ListBannersUseCase],
    actor: UserDto = Depends(require_admin),
) -> BannerListResponse:
    result = await use_case(actor)
    return BannerListResponse(
        banners=[_to_meta_response(banner) for banner in result.banners],
        available_locales=result.available_locales,
    )


@router.post("", response_model=BannerMetaResponse)
@inject
async def upload_banner(
    use_case: FromDishka[UploadBannerUseCase],
    name: str = Form(...),
    locale: Locale = Form(...),
    file: UploadFile = File(...),
    actor: UserDto = Depends(require_admin),
) -> BannerMetaResponse:
    # Bounded read -- don't buffer an arbitrarily large upload into memory
    # just to reject it for being oversized a moment later.
    data = await file.read(MAX_BANNER_SIZE_BYTES + 1)
    try:
        banner = await use_case(
            actor,
            UploadBannerInput(
                name=name, locale=locale, content_type=file.content_type or "", data=data
            ),
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_meta_response(banner)


@router.delete("/{name}/{locale}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_banner(
    name: str,
    locale: Locale,
    use_case: FromDishka[DeleteBannerUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(actor, BannerKeyDto(name=name, locale=locale))
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/{name}/{locale}/image")
@inject
async def get_banner_image(
    name: str,
    locale: Locale,
    use_case: FromDishka[GetBannerImageUseCase],
    actor: UserDto = Depends(require_admin),
) -> Response:
    try:
        data, content_type = await use_case(actor, BannerKeyDto(name=name, locale=locale))
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(content=data, media_type=content_type)


@router.post("/default/restore", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def restore_default_banner(
    use_case: FromDishka[RestoreDefaultBannerUseCase],
    actor: UserDto = Depends(require_admin),
) -> Response:
    await use_case(actor, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
