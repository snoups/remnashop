from dishka import Provider, Scope, provide

from app.modules.advertising.repository import AdLinkRepository
from app.modules.advertising.usecases import (
    CreateAdLinkUseCase,
    DeleteAdLinkUseCase,
    GenerateAdLinkCodeUseCase,
    GetAdLinkStatsUseCase,
    GetAdvertisingSummaryUseCase,
    ListAdLinkAttributedUsersUseCase,
    ListAdLinksUseCase,
    UpdateAdLinkUseCase,
)


class AdvertisingProvider(Provider):
    scope = Scope.REQUEST

    ad_link_repository = provide(AdLinkRepository)
    create_ad_link_use_case = provide(CreateAdLinkUseCase)
    update_ad_link_use_case = provide(UpdateAdLinkUseCase)
    delete_ad_link_use_case = provide(DeleteAdLinkUseCase)
    list_ad_links_use_case = provide(ListAdLinksUseCase)
    generate_ad_link_code_use_case = provide(GenerateAdLinkCodeUseCase)
    get_ad_link_stats_use_case = provide(GetAdLinkStatsUseCase)
    get_advertising_summary_use_case = provide(GetAdvertisingSummaryUseCase)
    list_ad_link_attributed_users_use_case = provide(ListAdLinkAttributedUsersUseCase)


def get_advertising_providers() -> list[Provider]:
    return [AdvertisingProvider()]
