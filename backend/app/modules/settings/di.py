from dishka import Provider, Scope, provide, provide_all

from app.core.ports import BotCommandsSync
from app.modules.settings.bot_commands_sync import BotCommandsPusher
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import (
    DeleteAppearanceFaviconUseCase,
    DeleteAppearanceLogoUseCase,
    GetAccessSettingsUseCase,
    GetBotCommandsUseCase,
    GetBotLogsUseCase,
    GetBotRequirementsUseCase,
    GetBotSettingsUseCase,
    GetBotStatusUseCase,
    GetCabinetAuthSettingsUseCase,
    GetEmailSettingsUseCase,
    GetOAuthSettingsUseCase,
    GetPublicAppearanceImageUseCase,
    GetPublicAppearanceUseCase,
    GetShopSettingsUseCase,
    RemoveBotProxyUseCase,
    ResetAppearanceSettingsUseCase,
    RestartBotUseCase,
    SetBotProxyUseCase,
    UpdateAccessSettingsUseCase,
    UpdateAppearanceSettingsUseCase,
    UpdateBotCommandsUseCase,
    UpdateBotRequirementsUseCase,
    UpdateBotSettingsUseCase,
    UpdateCabinetAuthSettingsUseCase,
    UpdateEmailSettingsUseCase,
    UpdateOAuthSettingsUseCase,
    UpdateShopSettingsUseCase,
    UploadAppearanceFaviconUseCase,
    UploadAppearanceLogoUseCase,
)


class SettingsProvider(Provider):
    scope = Scope.REQUEST

    settings_repository = provide(SettingsRepository)
    use_cases = provide_all(
        GetBotSettingsUseCase,
        GetBotStatusUseCase,
        GetBotLogsUseCase,
        UpdateBotSettingsUseCase,
        RestartBotUseCase,
        SetBotProxyUseCase,
        RemoveBotProxyUseCase,
        GetShopSettingsUseCase,
        GetAccessSettingsUseCase,
        UpdateAccessSettingsUseCase,
        GetEmailSettingsUseCase,
        UpdateEmailSettingsUseCase,
        GetCabinetAuthSettingsUseCase,
        UpdateCabinetAuthSettingsUseCase,
        GetBotRequirementsUseCase,
        UpdateBotRequirementsUseCase,
        UpdateShopSettingsUseCase,
        GetOAuthSettingsUseCase,
        UpdateOAuthSettingsUseCase,
        GetBotCommandsUseCase,
        UpdateBotCommandsUseCase,
        GetPublicAppearanceUseCase,
        GetPublicAppearanceImageUseCase,
        UpdateAppearanceSettingsUseCase,
        ResetAppearanceSettingsUseCase,
        UploadAppearanceLogoUseCase,
        UploadAppearanceFaviconUseCase,
        DeleteAppearanceLogoUseCase,
        DeleteAppearanceFaviconUseCase,
    )
    bot_commands_sync = provide(BotCommandsPusher, provides=BotCommandsSync)


def get_settings_providers() -> list[Provider]:
    return [SettingsProvider()]
