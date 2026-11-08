from app.modules.users.usecases.bind_telegram_id import BindTelegramIdUseCase
from app.modules.users.usecases.block_blacklist_matches import BlockBlacklistMatchesUseCase
from app.modules.users.usecases.block_user import BlockUserUseCase
from app.modules.users.usecases.clear_email_undeliverable import ClearEmailUndeliverableUseCase
from app.modules.users.usecases.create_admin import CreateAdminUseCase
from app.modules.users.usecases.delete_admin import DeleteAdminUseCase
from app.modules.users.usecases.delete_user import DeleteUserUseCase
from app.modules.users.usecases.demote_admin import DemoteAdminUseCase
from app.modules.users.usecases.find_telegram_user import FindTelegramUserUseCase
from app.modules.users.usecases.get_current_user import GetCurrentUserUseCase
from app.modules.users.usecases.get_user import GetUserUseCase
from app.modules.users.usecases.get_user_list_stats import GetUserListStatsUseCase
from app.modules.users.usecases.get_user_registration import GetUserRegistrationUseCase
from app.modules.users.usecases.list_admins import ListAdminsUseCase
from app.modules.users.usecases.list_blacklist_matches import ListBlacklistMatchesUseCase
from app.modules.users.usecases.list_users import ListUsersUseCase
from app.modules.users.usecases.promote_to_admin import PromoteToAdminUseCase
from app.modules.users.usecases.register_cabinet_user import RegisterCabinetUserUseCase
from app.modules.users.usecases.register_telegram_user import RegisterTelegramUserUseCase
from app.modules.users.usecases.set_bot_blocked import SetBotBlockedUseCase
from app.modules.users.usecases.set_marketing_opt_out import SetMarketingOptOutUseCase
from app.modules.users.usecases.set_user_discount import SetUserDiscountUseCase
from app.modules.users.usecases.set_user_trial_availability import (
    SetUserTrialAvailabilityUseCase,
)
from app.modules.users.usecases.unbind_telegram_id import UnbindTelegramIdUseCase
from app.modules.users.usecases.unblock_blacklist_matches import UnblockBlacklistMatchesUseCase
from app.modules.users.usecases.unblock_user import UnblockUserUseCase
from app.modules.users.usecases.unsubscribe_marketing import UnsubscribeMarketingUseCase
from app.modules.users.usecases.update_admin import UpdateAdminUseCase
from app.modules.users.usecases.update_own_profile import UpdateOwnProfileUseCase
from app.modules.users.usecases.update_own_security_settings import UpdateOwnSecuritySettingsUseCase

__all__ = [
    "BindTelegramIdUseCase",
    "BlacklistMatchOrigin",
    "BlockBlacklistMatchesUseCase",
    "BlockUserUseCase",
    "ClearEmailUndeliverableUseCase",
    "CreateAdminUseCase",
    "DeleteAdminUseCase",
    "DeleteUserUseCase",
    "DemoteAdminUseCase",
    "FindTelegramUserUseCase",
    "GetCurrentUserUseCase",
    "GetUserListStatsUseCase",
    "GetUserRegistrationUseCase",
    "GetUserUseCase",
    "ListAdminsUseCase",
    "ListBlacklistMatchesUseCase",
    "ListUsersUseCase",
    "PromoteToAdminUseCase",
    "RegisterCabinetUserUseCase",
    "RegisterTelegramUserUseCase",
    "SetBotBlockedUseCase",
    "SetMarketingOptOutUseCase",
    "SetUserDiscountDto",
    "SetUserDiscountUseCase",
    "SetUserTrialAvailabilityUseCase",
    "UnbindTelegramIdUseCase",
    "UnblockBlacklistMatchesUseCase",
    "UnblockUserUseCase",
    "UnsubscribeMarketingUseCase",
    "UpdateAdminUseCase",
    "UpdateOwnProfileUseCase",
    "UpdateOwnSecuritySettingsUseCase",
]
