from app.modules.users.usecases.accept_rules import AcceptRulesUseCase
from app.modules.users.usecases.bind_telegram_id import BindTelegramIdUseCase
from app.modules.users.usecases.block_blacklist_matches import BlockBlacklistMatchesUseCase
from app.modules.users.usecases.block_user import BlockUserUseCase
from app.modules.users.usecases.create_admin import CreateAdminUseCase
from app.modules.users.usecases.delete_admin import DeleteAdminUseCase
from app.modules.users.usecases.delete_user import DeleteUserUseCase
from app.modules.users.usecases.demote_admin import DemoteAdminUseCase
from app.modules.users.usecases.get_current_user import GetCurrentUserUseCase
from app.modules.users.usecases.get_user import GetUserUseCase
from app.modules.users.usecases.get_user_list_stats import GetUserListStatsUseCase
from app.modules.users.usecases.list_admins import ListAdminsUseCase
from app.modules.users.usecases.list_blacklist_matches import ListBlacklistMatchesUseCase
from app.modules.users.usecases.list_users import ListUsersUseCase
from app.modules.users.usecases.promote_to_admin import PromoteToAdminUseCase
from app.modules.users.usecases.register_cabinet_user import RegisterCabinetUserUseCase
from app.modules.users.usecases.register_telegram_user import RegisterTelegramUserUseCase
from app.modules.users.usecases.set_marketing_opt_out import SetMarketingOptOutUseCase
from app.modules.users.usecases.set_user_discount import SetUserDiscountUseCase
from app.modules.users.usecases.unblock_all_users import UnblockAllUsersUseCase
from app.modules.users.usecases.unblock_blacklist_matches import UnblockBlacklistMatchesUseCase
from app.modules.users.usecases.unblock_user import UnblockUserUseCase
from app.modules.users.usecases.update_admin import UpdateAdminUseCase
from app.modules.users.usecases.update_own_profile import UpdateOwnProfileUseCase
from app.modules.users.usecases.update_own_security_settings import UpdateOwnSecuritySettingsUseCase

__all__ = [
    "AcceptRulesUseCase",
    "BindTelegramIdUseCase",
    "BlacklistMatchOrigin",
    "BlockBlacklistMatchesUseCase",
    "BlockUserUseCase",
    "CreateAdminUseCase",
    "DeleteAdminUseCase",
    "DeleteUserUseCase",
    "DemoteAdminUseCase",
    "GetCurrentUserUseCase",
    "GetUserListStatsUseCase",
    "GetUserUseCase",
    "ListAdminsUseCase",
    "ListBlacklistMatchesUseCase",
    "ListUsersUseCase",
    "PromoteToAdminUseCase",
    "RegisterCabinetUserUseCase",
    "RegisterTelegramUserUseCase",
    "SetMarketingOptOutUseCase",
    "SetUserDiscountDto",
    "SetUserDiscountUseCase",
    "UnblockAllUsersUseCase",
    "UnblockBlacklistMatchesUseCase",
    "UnblockUserUseCase",
    "UpdateAdminUseCase",
    "UpdateOwnProfileUseCase",
    "UpdateOwnSecuritySettingsUseCase",
]
