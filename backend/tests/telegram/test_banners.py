from pathlib import Path

from aiogram.enums import ContentType

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.modules.banners.dto import UploadBannerDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import save_banner_file
from app.modules.banners.usecases import GetBannerForDisplayUseCase
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import UserDto
from app.telegram.banners import get_banner_media

USER = UserDto(id=1, name="u", language=Locale.RU)


def _config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


async def test_get_banner_media_returns_none_when_not_found(
    banner_repository: BannerRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    cfg = _config(config, tmp_path)
    media = await get_banner_media(
        GetBannerForDisplayUseCase(
            banner_repository, TranslationRepository(banner_repository.session), uow
        ),
        cfg,
        USER,
        "menu",
    )
    assert media is None


async def test_get_banner_media_sends_a_gif_as_an_animation(
    banner_repository: BannerRepository,
    config: AppConfig,
    uow: UnitOfWork,
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

    media = await get_banner_media(
        GetBannerForDisplayUseCase(
            banner_repository, TranslationRepository(banner_repository.session), uow
        ),
        cfg,
        USER,
        "menu",
    )
    assert media is not None
    assert media.type == ContentType.ANIMATION
