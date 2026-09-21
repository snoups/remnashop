from pathlib import Path

from app.core.config import AppConfig
from app.core.constants import DEFAULT_BANNER_NAME
from app.modules.banners.repository import BannerRepository
from app.modules.banners.seed import ensure_default_banner_seeded, restore_default_banner
from app.modules.banners.storage import banner_path


async def test_seeding_writes_the_shipped_picture(
    banner_repository: BannerRepository, config: AppConfig, tmp_path: Path
) -> None:
    config = config.model_copy(update={"media_dir": tmp_path})
    await ensure_default_banner_seeded(banner_repository, config)

    banner = await banner_repository.get(DEFAULT_BANNER_NAME, config.default_locale)
    assert banner is not None
    assert banner.size_bytes > 0
    assert banner_path(tmp_path, DEFAULT_BANNER_NAME, config.default_locale, "png").exists()


async def test_seeding_leaves_an_uploaded_banner_alone(
    banner_repository: BannerRepository, config: AppConfig, tmp_path: Path
) -> None:
    # Whatever the admin uploaded is theirs -- a restart must not overwrite it.
    config = config.model_copy(update={"media_dir": tmp_path})
    await restore_default_banner(banner_repository, config)
    replaced = await banner_repository.upsert(
        (await banner_repository.get(DEFAULT_BANNER_NAME, config.default_locale)).model_copy(  # type: ignore[union-attr]
            update={"size_bytes": 1, "content_type": "image/gif", "extension": "gif"}
        )
    )
    await ensure_default_banner_seeded(banner_repository, config)

    banner = await banner_repository.get(DEFAULT_BANNER_NAME, config.default_locale)
    assert banner is not None
    assert banner.extension == replaced.extension
