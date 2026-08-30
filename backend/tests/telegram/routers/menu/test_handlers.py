from pathlib import Path
from unittest.mock import AsyncMock

from aiogram.types import Message

from app.core.config import AppConfig
from app.core.enums import BannerName, Locale
from app.modules.banners.dto import UploadBannerDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import save_banner_file
from app.modules.settings.dto import UpdateBotSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto
from app.telegram.routers.menu.handlers import on_menu


def _message() -> Message:
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.answer_photo = AsyncMock()
    message.answer_animation = AsyncMock()
    return message


def _config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


async def test_on_menu_sends_text_only_when_banners_disabled(
    tmp_path: Path,
    config: AppConfig,
    settings_repository: SettingsRepository,
    banner_repository: BannerRepository,
) -> None:
    message = _message()
    user = UserDto(name="Alice", language=Locale.EN)

    await on_menu(message, user, _config(config, tmp_path), settings_repository, banner_repository)

    message.answer.assert_awaited_once()
    message.answer_photo.assert_not_awaited()


async def test_on_menu_sends_photo_when_banner_found(
    tmp_path: Path,
    config: AppConfig,
    settings_repository: SettingsRepository,
    banner_repository: BannerRepository,
) -> None:
    cfg = _config(config, tmp_path)
    await settings_repository.update_bot_settings(UpdateBotSettingsDto(banners_enabled=True))
    await banner_repository.upsert(
        UploadBannerDto(
            name=BannerName.MENU,
            locale=Locale.EN,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=8,
        )
    )
    save_banner_file(cfg.media_dir, BannerName.MENU, Locale.EN, "jpg", b"fake-jpg")

    message = _message()
    user = UserDto(name="Alice", language=Locale.EN)

    await on_menu(message, user, cfg, settings_repository, banner_repository)

    message.answer_photo.assert_awaited_once()
    message.answer.assert_not_awaited()


async def test_on_menu_falls_back_to_text_when_banner_missing(
    tmp_path: Path,
    config: AppConfig,
    settings_repository: SettingsRepository,
    banner_repository: BannerRepository,
) -> None:
    await settings_repository.update_bot_settings(UpdateBotSettingsDto(banners_enabled=True))

    message = _message()
    user = UserDto(name="Alice", language=Locale.EN)

    await on_menu(message, user, _config(config, tmp_path), settings_repository, banner_repository)

    message.answer.assert_awaited_once()
    message.answer_photo.assert_not_awaited()
