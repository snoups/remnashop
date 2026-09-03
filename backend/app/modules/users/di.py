from dishka import Provider, Scope, provide

from app.modules.users.repository import UserRepository
from app.modules.users.usecases import (
    BlockUserUseCase,
    BulkBlockUsersUseCase,
    CreateAdminUseCase,
    DeleteAdminUseCase,
    DeleteUserUseCase,
    DemoteAdminUseCase,
    GetCurrentUserUseCase,
    ListAdminsUseCase,
    ListUsersUseCase,
    PromoteToAdminUseCase,
    RegisterTelegramUserUseCase,
    SetUserPersonalDiscountUseCase,
    UnblockAllUsersUseCase,
    UnblockUserUseCase,
    UpdateAdminUseCase,
    UpdateOwnProfileUseCase,
    UpdateOwnSecuritySettingsUseCase,
)


class UsersProvider(Provider):
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
    set_user_personal_discount_use_case = provide(SetUserPersonalDiscountUseCase)
    block_user_use_case = provide(BlockUserUseCase)
    unblock_user_use_case = provide(UnblockUserUseCase)
    bulk_block_users_use_case = provide(BulkBlockUsersUseCase)
    unblock_all_users_use_case = provide(UnblockAllUsersUseCase)


def get_users_providers() -> list[Provider]:
    return [UsersProvider()]
