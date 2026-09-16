from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.modules.settings import SettingsRepository, push_bot_commands_to_telegram
from app.modules.translations.repository import TranslationsRepository


async def repush_bot_commands_if_configured(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    config: AppConfig,
    uow: UnitOfWork,
) -> None:
    async with uow:
        bot_settings = await settings_repository.get_bot_settings()
    if not bot_settings.is_configured:
        return

    # Lazy import -- GetBotCommandsUseCase sits behind settings' own di import,
    # which is what makes the settings<->translations cycle circular in the
    # first place; deferring to call time (after both packages are fully
    # loaded) sidesteps it.
    from app.modules.settings import GetBotCommandsUseCase  # noqa: PLC0415

    commands = await GetBotCommandsUseCase(settings_repository, uow).system()
    enabled = [item for item in commands if item.enabled]
    async with uow:
        active_locales = await settings_repository.list_active_locales()
        translations_by_locale = await translations_repository.get_fluent_text_by_locale(
            active_locales
        )
    token = bot_settings.token.get_secret_value() if bot_settings.token is not None else None
    await push_bot_commands_to_telegram(
        token,
        enabled,
        active_locales,
        translations_by_locale,
        config.default_locale,
    )
