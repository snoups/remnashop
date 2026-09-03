from app.modules.users.dto import BulkBlockResultDto, SetUserPersonalDiscountDto
from app.modules.users.usecases.block_user import BlockUserUseCase
from app.modules.users.usecases.bulk_block_users import BulkBlockUsersUseCase
from app.modules.users.usecases.create_admin import CreateAdminDto, CreateAdminUseCase
from app.modules.users.usecases.delete_admin import DeleteAdminDto, DeleteAdminUseCase
from app.modules.users.usecases.delete_user import DeleteUserDto, DeleteUserUseCase
from app.modules.users.usecases.demote_admin import DemoteAdminDto, DemoteAdminUseCase
from app.modules.users.usecases.get_current_user import GetCurrentUserUseCase
from app.modules.users.usecases.list_admins import ListAdminsUseCase
from app.modules.users.usecases.list_users import ListUsersInput, ListUsersUseCase
from app.modules.users.usecases.promote_to_admin import PromoteToAdminDto, PromoteToAdminUseCase
from app.modules.users.usecases.register_telegram_user import (
    RegisterTelegramUserDto,
    RegisterTelegramUserUseCase,
)
from app.modules.users.usecases.set_user_personal_discount import SetUserPersonalDiscountUseCase
from app.modules.users.usecases.unblock_all_users import UnblockAllUsersUseCase
from app.modules.users.usecases.unblock_user import UnblockUserUseCase
from app.modules.users.usecases.update_admin import UpdateAdminDto, UpdateAdminUseCase
from app.modules.users.usecases.update_own_profile import (
    UpdateOwnProfileDto,
    UpdateOwnProfileUseCase,
)
from app.modules.users.usecases.update_own_security_settings import (
    UpdateOwnSecuritySettingsUseCase,
    UpdateSecuritySettingsDto,
)

__all__ = [
    "BlockUserUseCase",
    "BulkBlockResultDto",
    "BulkBlockUsersUseCase",
    "CreateAdminDto",
    "CreateAdminUseCase",
    "DeleteAdminDto",
    "DeleteAdminUseCase",
    "DeleteUserDto",
    "DeleteUserUseCase",
    "DemoteAdminDto",
    "DemoteAdminUseCase",
    "GetCurrentUserUseCase",
    "ListAdminsUseCase",
    "ListUsersInput",
    "ListUsersUseCase",
    "PromoteToAdminDto",
    "PromoteToAdminUseCase",
    "RegisterTelegramUserDto",
    "RegisterTelegramUserUseCase",
    "SetUserPersonalDiscountDto",
    "SetUserPersonalDiscountUseCase",
    "UnblockAllUsersUseCase",
    "UnblockUserUseCase",
    "UpdateAdminDto",
    "UpdateAdminUseCase",
    "UpdateOwnProfileDto",
    "UpdateOwnProfileUseCase",
    "UpdateOwnSecuritySettingsUseCase",
    "UpdateSecuritySettingsDto",
]
