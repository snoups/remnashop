from dishka import Provider, Scope, provide, provide_all

from app.modules.banners.repository import BannerRepository
from app.modules.banners.seed import DefaultBannerSeeder
from app.modules.banners.usecases import (
    DeleteBannerUseCase,
    GetBannerForDisplayUseCase,
    GetBannerImageUseCase,
    RestoreDefaultBannerUseCase,
    UploadBannerUseCase,
)
from app.modules.translations import DefaultBannerSeed


class BannersProvider(Provider):
    scope = Scope.REQUEST

    banner_repository = provide(BannerRepository)
    default_banner_seed = provide(DefaultBannerSeeder, provides=DefaultBannerSeed)
    use_cases = provide_all(
        UploadBannerUseCase,
        DeleteBannerUseCase,
        GetBannerImageUseCase,
        RestoreDefaultBannerUseCase,
        GetBannerForDisplayUseCase,
    )


def get_banners_providers() -> list[Provider]:
    return [BannersProvider()]
