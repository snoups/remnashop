from app.core.config import AppConfig
from app.core.constants import WINDOW_BANNER_PREFIX
from app.modules.banners import BannerRepository, delete_banner_file


async def drop_window_banners(
    banner_repository: BannerRepository, config: AppConfig, window_key: str
) -> None:
    """A window's own banner is named after its key and nothing else points at
    it, so it dies with the window instead of lingering in the media dir."""
    orphaned = await banner_repository.delete_all_named(f"{WINDOW_BANNER_PREFIX}{window_key}")
    for banner in orphaned:
        delete_banner_file(config.media_dir, banner.name, banner.locale, banner.extension)
