from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.modules.blacklist import ReconcileBlacklistDispatch
from app.modules.users.blacklist_repository import UserBlacklistRepository
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from app.modules.users.tasks import reconcile_blacklist_task
from app.modules.users.usecases import (
    BlockBlacklistMatchesUseCase,
    BlockUserUseCase,
    CreateAdminUseCase,
    DeleteAdminUseCase,
    DeleteUserUseCase,
    DemoteAdminUseCase,
    GetCurrentUserUseCase,
    GetUserListStatsUseCase,
    GetUserUseCase,
    ListAdminsUseCase,
    ListBlacklistMatchesUseCase,
    ListUsersUseCase,
    PromoteToAdminUseCase,
    RegisterTelegramUserUseCase,
    SetUserDiscountUseCase,
    UnblockAllUsersUseCase,
    UnblockBlacklistMatchesUseCase,
    UnblockUserUseCase,
    UpdateAdminUseCase,
    UpdateOwnProfileUseCase,
    UpdateOwnSecuritySettingsUseCase,
)


class UsersProvider(Provider):
    scope = Scope.REQUEST

    repositories = provide_all(
        UserRepository,
        UserStatsRepository,
        UserBlacklistRepository,
    )
    use_cases = provide_all(
        GetCurrentUserUseCase,
        ListAdminsUseCase,
        ListUsersUseCase,
        GetUserUseCase,
        GetUserListStatsUseCase,
        ListBlacklistMatchesUseCase,
        CreateAdminUseCase,
        PromoteToAdminUseCase,
        UpdateAdminUseCase,
        DemoteAdminUseCase,
        DeleteAdminUseCase,
        DeleteUserUseCase,
        UpdateOwnProfileUseCase,
        UpdateOwnSecuritySettingsUseCase,
        RegisterTelegramUserUseCase,
        SetUserDiscountUseCase,
        BlockUserUseCase,
        UnblockUserUseCase,
        UnblockAllUsersUseCase,
        UnblockBlacklistMatchesUseCase,
        BlockBlacklistMatchesUseCase,
    )

    @provide(scope=Scope.APP)
    def reconcile_blacklist_dispatch(self) -> ReconcileBlacklistDispatch:
        return cast(ReconcileBlacklistDispatch, reconcile_blacklist_task)


def get_users_providers() -> list[Provider]:
    return [UsersProvider()]
