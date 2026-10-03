from dishka import Provider, Scope, provide, provide_all

from app.modules.announcements.repository import AnnouncementRepository
from app.modules.announcements.usecases import (
    DismissAnnouncementsUseCase,
    ListAnnouncementsUseCase,
    MarkAnnouncementsSeenUseCase,
    SyncAnnouncementsUseCase,
)


class AnnouncementsProvider(Provider):
    scope = Scope.REQUEST

    announcement_repository = provide(AnnouncementRepository)
    use_cases = provide_all(
        DismissAnnouncementsUseCase,
        ListAnnouncementsUseCase,
        MarkAnnouncementsSeenUseCase,
        SyncAnnouncementsUseCase,
    )


def get_announcements_providers() -> list[Provider]:
    return [AnnouncementsProvider()]
