from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models.bot_translation import BotTranslation
from app.core.enums import Locale
from app.modules.settings.repository import SettingsRepository
from app.modules.translations.repository import TranslationRepository
from app.modules.translations.seed import ensure_translations_seeded


def _seed_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    translations_dir = tmp_path / "translations"
    (translations_dir / "en").mkdir(parents=True)
    (translations_dir / "ru").mkdir(parents=True)
    (translations_dir / "en" / "commands.ftl").write_text(
        "command =\n    .menu = Open the main menu\n"
    )
    (translations_dir / "ru" / "commands.ftl").write_text(
        "command =\n    .menu = Открыть главное меню\n"
    )
    return config.model_copy(update={"assets_dir": tmp_path})


async def test_seeds_en_and_ru_from_ftl_files(
    tmp_path: Path,
    config: AppConfig,
    translation_repository: TranslationRepository,
    settings_repository: SettingsRepository,
) -> None:
    await ensure_translations_seeded(_seed_config(config, tmp_path), translation_repository)

    en_entry = await translation_repository.get(Locale.EN, "command", "menu")
    ru_entry = await translation_repository.get(Locale.RU, "command", "menu")
    assert en_entry is not None and en_entry.value == "Open the main menu"
    assert ru_entry is not None and ru_entry.value == "Открыть главное меню"
    assert set(await translation_repository.list_active_locales()) == {Locale.EN, Locale.RU}


async def test_seeding_is_idempotent_and_does_not_overwrite_edits(
    tmp_path: Path,
    config: AppConfig,
    translation_repository: TranslationRepository,
    settings_repository: SettingsRepository,
) -> None:
    seed_config = _seed_config(config, tmp_path)
    await ensure_translations_seeded(seed_config, translation_repository)
    await translation_repository.update_value(Locale.EN, "command", "menu", "Admin-edited text")

    await ensure_translations_seeded(seed_config, translation_repository)

    entry = await translation_repository.get(Locale.EN, "command", "menu")
    assert entry is not None
    assert entry.value == "Admin-edited text"


async def test_seeding_does_not_resurrect_a_removed_locale(
    tmp_path: Path,
    config: AppConfig,
    session: AsyncSession,
    translation_repository: TranslationRepository,
    settings_repository: SettingsRepository,
) -> None:
    seed_config = _seed_config(config, tmp_path)
    await ensure_translations_seeded(seed_config, translation_repository)
    await translation_repository.remove_active_locale(Locale.RU)
    await session.execute(delete(BotTranslation).where(BotTranslation.locale == Locale.RU))

    await ensure_translations_seeded(seed_config, translation_repository)

    assert Locale.RU not in await translation_repository.list_active_locales()
    assert await translation_repository.get(Locale.RU, "command", "menu") is None


async def test_seeds_menu_ftl_alongside_commands_ftl(
    tmp_path: Path,
    config: AppConfig,
    translation_repository: TranslationRepository,
    settings_repository: SettingsRepository,
) -> None:
    seed_config = _seed_config(config, tmp_path)
    (tmp_path / "translations" / "en" / "menu.ftl").write_text("msg-main-menu = Main menu\n")

    await ensure_translations_seeded(seed_config, translation_repository)

    entry = await translation_repository.get(Locale.EN, "msg-main-menu", "")
    assert entry is not None and entry.value == "Main menu"


async def test_seeding_only_activates_locales_with_a_seed_file(
    tmp_path: Path,
    config: AppConfig,
    translation_repository: TranslationRepository,
    settings_repository: SettingsRepository,
) -> None:
    translations_dir = tmp_path / "translations" / "en"
    translations_dir.mkdir(parents=True)
    (translations_dir / "commands.ftl").write_text("command =\n    .menu = Open the main menu\n")
    en_only_config = config.model_copy(update={"assets_dir": tmp_path})

    await ensure_translations_seeded(en_only_config, translation_repository)

    assert await translation_repository.list_active_locales() == [Locale.EN]
