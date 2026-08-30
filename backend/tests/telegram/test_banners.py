from pathlib import Path

from app.core.config import AppConfig
from app.core.enums import BannerName, Locale
from app.modules.banners.dto import UploadBannerDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import save_banner_file
from app.telegram.banners import get_banner


def _config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


async def test_get_banner_returns_none_when_nothing_uploaded(
    banner_repository: BannerRepository, config: AppConfig, tmp_path: Path
) -> None:
    result = await get_banner(
        banner_repository, _config(config, tmp_path), BannerName.MENU, Locale.RU, Locale.EN
    )
    assert result is None


async def test_get_banner_reads_bytes_for_exact_match(
    banner_repository: BannerRepository, config: AppConfig, tmp_path: Path
) -> None:
    cfg = _config(config, tmp_path)
    await banner_repository.upsert(
        UploadBannerDto(
            name=BannerName.MENU,
            locale=Locale.RU,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=8,
        )
    )
    save_banner_file(cfg.media_dir, BannerName.MENU, Locale.RU, "jpg", b"fake-jpg")

    result = await get_banner(banner_repository, cfg, BannerName.MENU, Locale.RU, Locale.EN)

    assert result is not None
    data, content_type = result
    assert data == b"fake-jpg"
    assert content_type.value == "photo"


async def test_get_banner_resolves_gif_as_animation(
    banner_repository: BannerRepository, config: AppConfig, tmp_path: Path
) -> None:
    cfg = _config(config, tmp_path)
    await banner_repository.upsert(
        UploadBannerDto(
            name=BannerName.MENU,
            locale=Locale.RU,
            content_type="image/gif",
            extension="gif",
            size_bytes=8,
        )
    )
    save_banner_file(cfg.media_dir, BannerName.MENU, Locale.RU, "gif", b"fake-gif")

    result = await get_banner(banner_repository, cfg, BannerName.MENU, Locale.RU, Locale.EN)

    assert result is not None
    _, content_type = result
    assert content_type.value == "animation"


async def test_get_banner_returns_none_when_file_missing_on_disk(
    banner_repository: BannerRepository, config: AppConfig, tmp_path: Path
) -> None:
    cfg = _config(config, tmp_path)
    await banner_repository.upsert(
        UploadBannerDto(
            name=BannerName.MENU,
            locale=Locale.RU,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=8,
        )
    )

    result = await get_banner(banner_repository, cfg, BannerName.MENU, Locale.RU, Locale.EN)

    assert result is None


async def test_get_banner_uses_locale_fallback(
    banner_repository: BannerRepository, config: AppConfig, tmp_path: Path
) -> None:
    cfg = _config(config, tmp_path)
    await banner_repository.upsert(
        UploadBannerDto(
            name=BannerName.DEFAULT,
            locale=Locale.EN,
            content_type="image/png",
            extension="png",
            size_bytes=8,
        )
    )
    save_banner_file(cfg.media_dir, BannerName.DEFAULT, Locale.EN, "png", b"fake-png")

    result = await get_banner(banner_repository, cfg, BannerName.MENU, Locale.RU, Locale.EN)

    assert result is not None
    data, _ = result
    assert data == b"fake-png"
