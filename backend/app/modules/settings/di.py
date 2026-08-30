from dishka import Provider, Scope, provide

from app.modules.settings.repository import SettingsRepository
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
    UploadAppearanceLogoUseCase,
)


class SettingsProvider(Provider):
    scope = Scope.REQUEST

    settings_repository = provide(SettingsRepository)
    get_bot_settings_use_case = provide(GetBotSettingsUseCase)
    update_bot_settings_use_case = provide(UpdateBotSettingsUseCase)
    restart_bot_use_case = provide(RestartBotUseCase)
    get_oauth_settings_use_case = provide(GetOAuthSettingsUseCase)
    update_oauth_settings_use_case = provide(UpdateOAuthSettingsUseCase)
    get_bot_commands_use_case = provide(GetBotCommandsUseCase)
    update_bot_commands_use_case = provide(UpdateBotCommandsUseCase)
    list_active_locales_use_case = provide(ListActiveLocalesUseCase)
    add_locale_use_case = provide(AddLocaleUseCase)
    remove_locale_use_case = provide(RemoveLocaleUseCase)
    get_public_appearance_use_case = provide(GetPublicAppearanceUseCase)
    get_public_appearance_image_use_case = provide(GetPublicAppearanceImageUseCase)
    update_appearance_settings_use_case = provide(UpdateAppearanceSettingsUseCase)
    reset_appearance_settings_use_case = provide(ResetAppearanceSettingsUseCase)
    upload_appearance_logo_use_case = provide(UploadAppearanceLogoUseCase)
    upload_appearance_favicon_use_case = provide(UploadAppearanceFaviconUseCase)
    delete_appearance_logo_use_case = provide(DeleteAppearanceLogoUseCase)
    delete_appearance_favicon_use_case = provide(DeleteAppearanceFaviconUseCase)


def get_settings_providers() -> list[Provider]:
    return [SettingsProvider()]
