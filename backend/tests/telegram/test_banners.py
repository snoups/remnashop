from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

from aiogram.enums import ContentType
from aiogram_dialog.api.entities import MediaAttachment

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.utils.telegram_text import TELEGRAM_CAPTION_LIMIT
from app.modules.banners.dto import UploadBannerDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import save_banner_file
from app.modules.banners.usecases import GetBannerForDisplayUseCase
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import UserDto
from app.telegram.banners import get_banner_media, with_window_banner

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


async def _window_getter(**kwargs: object) -> dict[str, object]:
    return {"window_text": kwargs["text"]}


async def _wrapped(banner_name: Optional[str], text: str, tmp_path: Path) -> dict[str, object]:
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: USER}
    cache = MagicMock()
    cache.get_window = AsyncMock(return_value=MagicMock(banner_name=banner_name))
    banner = MagicMock(locale=Locale.RU, extension="jpg", content_type="image/jpeg")
    banner.name = "default"
    get_banner = AsyncMock(return_value=banner)
    getter = with_window_banner("subscriptions.list", _window_getter)
    return await getter.__dishka_orig_func__(  # type: ignore[attr-defined, no-any-return]
        dialog_manager=manager,
        config=MagicMock(media_dir=tmp_path),
        get_banner=get_banner,
        dialog_config_cache=cache,
        text=text,
    )


async def test_window_banner_joins_a_code_defined_window(tmp_path: Path) -> None:
    data = await _wrapped("default", "short", tmp_path)

    assert data["window_text"] == "short"
    banner = data["banner"]
    assert isinstance(banner, MediaAttachment) and banner.type == ContentType.PHOTO


async def test_window_banner_is_dropped_for_a_text_past_the_caption_limit(tmp_path: Path) -> None:
    data = await _wrapped("default", "x" * (TELEGRAM_CAPTION_LIMIT + 1), tmp_path)

    assert data["banner"] is None


async def test_window_banner_follows_a_window_without_one(tmp_path: Path) -> None:
    data = await _wrapped(None, "short", tmp_path)

    assert data["banner"] is None
