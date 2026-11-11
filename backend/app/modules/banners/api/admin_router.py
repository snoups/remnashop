from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.api.uploads import MULTIPART_FILE_BODY, read_form_file
from app.core.actor import Actor
from app.core.enums import Locale
from app.modules.banners.api.schemas import BannerMetaResponse
from app.modules.banners.dto import BannerImageQueryDto, BannerKeyDto, UploadBannerFileDto
from app.modules.banners.storage import MAX_BANNER_SIZE_BYTES
from app.modules.banners.usecases import (
    DeleteBannerUseCase,
    GetBannerImageUseCase,
    RestoreDefaultBannerUseCase,
    UploadBannerUseCase,
)

router = APIRouter(prefix="/banners", tags=["banners"])

BANNER_NAME_HEADER: Final[str] = "X-Banner-Name"
BANNER_LOCALE_HEADER: Final[str] = "X-Banner-Locale"


@router.put(
    "/{name}/{locale}",
    response_model=BannerMetaResponse,
    responses=error_responses(400),
    openapi_extra=MULTIPART_FILE_BODY,
)
@inject
async def upload_banner(
    name: str,
    locale: Locale,
    request: Request,
    use_case: FromDishka[UploadBannerUseCase],
    actor: Actor = Depends(require_admin),
) -> BannerMetaResponse:
    file = await read_form_file(request, MAX_BANNER_SIZE_BYTES)
    banner = await use_case(
        actor,
        UploadBannerFileDto(
            name=name, locale=locale, content_type=file.content_type, data=file.data
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
    fallback: bool = False,
    actor: Actor = Depends(require_admin),
) -> Response:
    image = await use_case(actor, BannerImageQueryDto(name=name, locale=locale, fallback=fallback))
    # which file answered: with fallback it may be the shared banner or the default language's
    return Response(
        content=image.data,
        media_type=image.content_type,
        headers={BANNER_NAME_HEADER: image.name, BANNER_LOCALE_HEADER: image.locale.value},
    )


@router.post("/actions/reset-default", response_model=BannerMetaResponse)
@inject
async def reset_default_banner(
    use_case: FromDishka[RestoreDefaultBannerUseCase],
    actor: Actor = Depends(require_admin),
) -> BannerMetaResponse:
    return BannerMetaResponse.model_validate(await use_case(actor), from_attributes=True)
