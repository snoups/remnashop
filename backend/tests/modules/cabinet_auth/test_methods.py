import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.modules.cabinet_auth.usecases import GetCabinetMethodsUseCase
from app.modules.settings.dto import (
    UpdateBotSettingsDto,
    UpdateCabinetAuthSettingsDto,
    UpdateEmailSettingsDto,
    UpdateOAuthSettingsDto,
)
from app.modules.settings.repository import SettingsRepository


@pytest.fixture
def cabinet_config(config: AppConfig) -> AppConfig:
    return config.model_copy(update={"web_cabinet_url": "https://cabinet.example.com"})


async def test_methods_empty_by_default(
    settings_repository: SettingsRepository, cabinet_config: AppConfig, uow: UnitOfWork
) -> None:
    methods = await GetCabinetMethodsUseCase(settings_repository, cabinet_config, uow).execute()
    assert (methods.telegram_webapp, methods.email, methods.oauth) == (False, False, [])


async def test_enabled_method_hidden_until_configured(
    settings_repository: SettingsRepository, cabinet_config: AppConfig, uow: UnitOfWork
) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(telegram_enabled=True)
        )
    methods = await GetCabinetMethodsUseCase(settings_repository, cabinet_config, uow).execute()
    assert not methods.telegram_webapp

    async with uow:
        await settings_repository.update_bot_settings(
            UpdateBotSettingsDto(token="1:abc", secret_token="s")
        )
    methods = await GetCabinetMethodsUseCase(settings_repository, cabinet_config, uow).execute()
    assert methods.telegram_webapp and methods.telegram_deeplink


async def test_email_method_needs_smtp(
    settings_repository: SettingsRepository, cabinet_config: AppConfig, uow: UnitOfWork
) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(email_enabled=True)
        )
        await settings_repository.update_email_settings(
            UpdateEmailSettingsDto(host="smtp.example.com", from_address="a@b.c")
        )
    assert (
        await GetCabinetMethodsUseCase(settings_repository, cabinet_config, uow).execute()
    ).email


async def test_oauth_providers_need_cabinet_flag_and_credentials(
    settings_repository: SettingsRepository, cabinet_config: AppConfig, uow: UnitOfWork
) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(
                telegram_enabled=True, google_enabled=True, yandex_enabled=True
            )
        )
        await settings_repository.update_oauth_settings(
            UpdateOAuthSettingsDto(
                telegram_client_id="t",
                telegram_client_secret="t",
                google_client_id="g",
                google_client_secret="g",
            )
        )
    methods = await GetCabinetMethodsUseCase(settings_repository, cabinet_config, uow).execute()
    assert methods.oauth == [OAuthProvider.TELEGRAM, OAuthProvider.GOOGLE]

    async with uow:
        await settings_repository.update_oauth_settings(
            UpdateOAuthSettingsDto(yandex_client_id="y", yandex_client_secret="y")
        )
    methods = await GetCabinetMethodsUseCase(settings_repository, cabinet_config, uow).execute()
    assert methods.oauth == [OAuthProvider.TELEGRAM, OAuthProvider.GOOGLE, OAuthProvider.YANDEX]


async def test_oauth_list_is_empty_without_cabinet_url(
    settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork
) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(google_enabled=True)
        )
        await settings_repository.update_oauth_settings(
            UpdateOAuthSettingsDto(google_client_id="g", google_client_secret="g")
        )
    no_url = config.model_copy(update={"web_cabinet_url": ""})
    assert (await GetCabinetMethodsUseCase(settings_repository, no_url, uow).execute()).oauth == []
