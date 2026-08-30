# translations' usecases import SettingsRepository/push_bot_commands_to_telegram from
# this package, so those names must be bound before di pulls in usecases --
# otherwise the settings<->translations cycle fails on a partially initialized module.
from app.modules.settings.bootstrap import enable_password_login, read_bot_settings  # noqa: I001
from app.modules.settings.bot_commands import BOT_COMMANDS, BotCommand
from app.modules.settings.command_translations import (
    build_command_translator_hub,
    push_bot_commands_to_telegram,
)
from app.modules.settings.dto import (
    AppearanceSettingsDto,
    BotCommandDto,
    BotSettingsDto,
    OAuthSettingsDto,
    UpdateAppearanceSettingsDto,
    UpdateBotSettingsDto,
    UpdateOAuthSettingsDto,
)
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.di import get_settings_providers
from app.modules.settings.usecases import (
    AddLocaleUseCase,
    DeleteAppearanceFaviconUseCase,
    DeleteAppearanceLogoUseCase,
    GetBotCommandsUseCase,
    GetBotSettingsUseCase,
    GetOAuthSettingsUseCase,
    GetPublicAppearanceImageUseCase,
    GetPublicAppearanceUseCase,
    ListActiveLocalesUseCase,
    RemoveLocaleUseCase,
    ResetAppearanceSettingsUseCase,
    RestartBotUseCase,
    UpdateAppearanceSettingsUseCase,
    UpdateBotCommandsUseCase,
    UpdateBotSettingsUseCase,
    UpdateOAuthSettingsUseCase,
    UploadAppearanceFaviconUseCase,
    UploadAppearanceImageInput,
    UploadAppearanceLogoUseCase,
)

__all__ = [
    "BOT_COMMANDS",
    "AddLocaleUseCase",
    "AppearanceSettingsDto",
    "BotCommandDto",
    "BotSettingsDto",
    "DeleteAppearanceFaviconUseCase",
    "DeleteAppearanceLogoUseCase",
    "GetBotCommandsUseCase",
    "GetBotSettingsUseCase",
    "GetOAuthSettingsUseCase",
    "GetPublicAppearanceImageUseCase",
    "GetPublicAppearanceUseCase",
    "ListActiveLocalesUseCase",
    "BotCommand",
    "OAuthSettingsDto",
    "RemoveLocaleUseCase",
    "ResetAppearanceSettingsUseCase",
    "RestartBotUseCase",
    "SettingsRepository",
    "UpdateAppearanceSettingsDto",
    "UpdateAppearanceSettingsUseCase",
    "UpdateBotCommandsUseCase",
    "UpdateBotSettingsDto",
    "UpdateBotSettingsUseCase",
    "UpdateOAuthSettingsDto",
    "UpdateOAuthSettingsUseCase",
    "UploadAppearanceFaviconUseCase",
    "UploadAppearanceImageInput",
    "UploadAppearanceLogoUseCase",
    "build_command_translator_hub",
    "enable_password_login",
    "get_settings_providers",
    "push_bot_commands_to_telegram",
    "read_bot_settings",
]
