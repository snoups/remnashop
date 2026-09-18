from typing import Final

from app.modules.blacklist.dto import AddBlacklistSourceDto
from app.modules.blacklist.repository import BlacklistRepository

DEFAULT_SOURCE_URL: Final[str] = (
    "https://raw.githubusercontent.com/remnashop/blacklist/main/blacklist.txt"
)
_DEFAULT_SOURCE_NAME: Final[str] = "remnashop/blacklist"


async def ensure_blacklist_sources_seeded(blacklist_repository: BlacklistRepository) -> None:
    # Keyed on the URL: the caller decides when a deployment counts as fresh,
    # this only has to survive a restart before that point. Entries land on the
    # next sync (6h cron, or "Sync now").
    sources = await blacklist_repository.list_sources()
    if any(source.url == DEFAULT_SOURCE_URL for source in sources):
        return
    await blacklist_repository.add_source(
        AddBlacklistSourceDto(url=DEFAULT_SOURCE_URL, name=_DEFAULT_SOURCE_NAME)
    )
