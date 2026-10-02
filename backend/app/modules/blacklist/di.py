from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.modules.blacklist.dispatch import SyncBlacklistSourcesDispatch
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.blacklist.tasks import sync_blacklist_sources_task
from app.modules.blacklist.usecases import (
    AddBlacklistEntryUseCase,
    AddBlacklistSourceUseCase,
    FetchBlacklistSourcesUseCase,
    GetBlacklistSourceUseCase,
    ListBlacklistSourcesUseCase,
    ListBlacklistUseCase,
    RemoveBlacklistEntryUseCase,
    RemoveBlacklistSourceUseCase,
    SyncBlacklistSourcesUseCase,
    UpdateBlacklistSourceUseCase,
)


class BlacklistProvider(Provider):
    scope = Scope.REQUEST

    blacklist_repository = provide(BlacklistRepository)
    use_cases = provide_all(
        ListBlacklistUseCase,
        AddBlacklistEntryUseCase,
        RemoveBlacklistEntryUseCase,
        ListBlacklistSourcesUseCase,
        GetBlacklistSourceUseCase,
        AddBlacklistSourceUseCase,
        RemoveBlacklistSourceUseCase,
        UpdateBlacklistSourceUseCase,
        SyncBlacklistSourcesUseCase,
        FetchBlacklistSourcesUseCase,
    )

    @provide(scope=Scope.APP)
    def sync_blacklist_sources_dispatch(self) -> SyncBlacklistSourcesDispatch:
        return cast(SyncBlacklistSourcesDispatch, sync_blacklist_sources_task)


def get_blacklist_providers() -> list[Provider]:
    return [BlacklistProvider()]
