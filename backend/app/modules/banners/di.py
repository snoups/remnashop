from dishka import Provider, Scope, provide

from app.modules.banners.repository import BannerRepository
from app.modules.banners.usecases import (
    DeleteBannerUseCase,
    GetBannerImageUseCase,
    RestoreDefaultBannerUseCase,
    UploadBannerUseCase,
)


class BannersProvider(Provider):
    scope = Scope.REQUEST

    banner_repository = provide(BannerRepository)
    upload_banner_use_case = provide(UploadBannerUseCase)
    delete_banner_use_case = provide(DeleteBannerUseCase)
    get_banner_image_use_case = provide(GetBannerImageUseCase)
    restore_default_banner_use_case = provide(RestoreDefaultBannerUseCase)


def get_banners_providers() -> list[Provider]:
    return [BannersProvider()]
