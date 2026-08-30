from dishka import Provider, Scope, provide

from app.modules.banners.repository import BannerRepository
from app.modules.banners.usecases import (
    DeleteBannerUseCase,
    GetBannerImageUseCase,
    ListBannersUseCase,
    UploadBannerUseCase,
)


class BannerProvider(Provider):
    scope = Scope.REQUEST

    banner_repository = provide(BannerRepository)
    upload_banner_use_case = provide(UploadBannerUseCase)
    delete_banner_use_case = provide(DeleteBannerUseCase)
    list_banners_use_case = provide(ListBannersUseCase)
    get_banner_image_use_case = provide(GetBannerImageUseCase)


def get_banners_providers() -> list[Provider]:
    return [BannerProvider()]
