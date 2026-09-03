from dishka import Provider, Scope, provide

from app.modules.blacklist.repository import BlacklistRepository
from app.modules.blacklist.usecases import (
    AddBlacklistEntryUseCase,
    AddBlacklistSourceUseCase,
    ListBlacklistSourcesUseCase,
    ListBlacklistUseCase,
    RemoveBlacklistEntryUseCase,
    RemoveBlacklistSourceUseCase,
    SyncBlacklistSourcesUseCase,
    ToggleBlacklistSourceUseCase,
)


class BlacklistProvider(Provider):
    scope = Scope.REQUEST

    blacklist_repository = provide(BlacklistRepository)
    list_blacklist_use_case = provide(ListBlacklistUseCase)
    add_blacklist_entry_use_case = provide(AddBlacklistEntryUseCase)
    remove_blacklist_entry_use_case = provide(RemoveBlacklistEntryUseCase)
    list_blacklist_sources_use_case = provide(ListBlacklistSourcesUseCase)
    add_blacklist_source_use_case = provide(AddBlacklistSourceUseCase)
    remove_blacklist_source_use_case = provide(RemoveBlacklistSourceUseCase)
    toggle_blacklist_source_use_case = provide(ToggleBlacklistSourceUseCase)
    sync_blacklist_sources_use_case = provide(SyncBlacklistSourcesUseCase)


def get_blacklist_providers() -> list[Provider]:
    return [BlacklistProvider()]
