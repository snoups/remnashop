from dishka import Provider, Scope, provide, provide_all

from app.modules.advertising.repository import AdLinkRepository
from app.modules.advertising.usecases import (
    CreateAdLinkUseCase,
    DeleteAdLinkUseCase,
    GenerateAdLinkCodeUseCase,
    GetAdLinkPayoutUseCase,
    GetAdLinkShareUrlsUseCase,
    GetAdLinkStatsUseCase,
    GetAdLinkUseCase,
    GetAdvertisingSummaryUseCase,
    GetUserAdAttributionUseCase,
    ListAdLinkAttributedUsersUseCase,
    ListAdLinksUseCase,
    RecordAdLinkAttributionUseCase,
    UpdateAdLinkUseCase,
)


class AdvertisingProvider(Provider):
    scope = Scope.REQUEST

    ad_link_repository = provide(AdLinkRepository)
    use_cases = provide_all(
        CreateAdLinkUseCase,
        UpdateAdLinkUseCase,
        DeleteAdLinkUseCase,
        ListAdLinksUseCase,
        GetAdLinkUseCase,
        GenerateAdLinkCodeUseCase,
        GetAdLinkPayoutUseCase,
        GetAdLinkStatsUseCase,
        GetAdLinkShareUrlsUseCase,
        GetAdvertisingSummaryUseCase,
        ListAdLinkAttributedUsersUseCase,
        GetUserAdAttributionUseCase,
        RecordAdLinkAttributionUseCase,
    )


def get_advertising_providers() -> list[Provider]:
    return [AdvertisingProvider()]
