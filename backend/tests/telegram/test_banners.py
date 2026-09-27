from pathlib import Path

from aiogram.enums import ContentType

from app.core.config import AppConfig
from app.core.enums import Locale
from app.modules.banners.dto import UploadBannerDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import save_banner_file
from app.telegram.banners import get_banner_media


def _config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


async def test_get_banner_media_returns_none_when_not_found(
    banner_repository: BannerRepository, config: AppConfig, tmp_path: Path
) -> None:
    cfg = _config(config, tmp_path)
    media = await get_banner_media(banner_repository, cfg, "menu", Locale.RU, cfg.default_locale)
    assert media is None


async def test_get_banner_media_sends_a_gif_as_an_animation(
    banner_repository: BannerRepository,
    config: AppConfig,
    tmp_path: Path,
) -> None:
    cfg = _config(config, tmp_path)
    await banner_repository.upsert(
        UploadBannerDto(
            name="menu",
            locale=Locale.RU,
            content_type="image/gif",
            extension="gif",
            size_bytes=8,
        )
    )
    save_banner_file(cfg.media_dir, "menu", Locale.RU, "gif", b"fake-gif")

    media = await get_banner_media(banner_repository, cfg, "menu", Locale.RU, cfg.default_locale)
    assert media is not None
    assert media.type == ContentType.ANIMATION
