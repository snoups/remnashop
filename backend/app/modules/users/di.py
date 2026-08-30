from dishka import Provider, Scope, provide

from app.modules.users.repository import UserRepository
from app.modules.users.usecases import (
    CreateAdminUseCase,
    DeleteAdminUseCase,
    DeleteUserUseCase,
    DemoteAdminUseCase,
    GetCurrentUserUseCase,
    ListAdminsUseCase,
    ListUsersUseCase,
    PromoteToAdminUseCase,
    RegisterTelegramUserUseCase,
    UpdateAdminUseCase,
    UpdateOwnProfileUseCase,
    UpdateOwnSecuritySettingsUseCase,
)


class UserProvider(Provider):
    scope = Scope.REQUEST

    user_repository = provide(UserRepository)
    get_current_user_use_case = provide(GetCurrentUserUseCase)
    list_admins_use_case = provide(ListAdminsUseCase)
    list_users_use_case = provide(ListUsersUseCase)
    create_admin_use_case = provide(CreateAdminUseCase)
    promote_to_admin_use_case = provide(PromoteToAdminUseCase)
    update_admin_use_case = provide(UpdateAdminUseCase)
    demote_admin_use_case = provide(DemoteAdminUseCase)
    delete_admin_use_case = provide(DeleteAdminUseCase)
    delete_user_use_case = provide(DeleteUserUseCase)
    update_own_profile_use_case = provide(UpdateOwnProfileUseCase)
    update_own_security_settings_use_case = provide(UpdateOwnSecuritySettingsUseCase)
    register_telegram_user_use_case = provide(RegisterTelegramUserUseCase)


def get_user_providers() -> list[Provider]:
    return [UserProvider()]
