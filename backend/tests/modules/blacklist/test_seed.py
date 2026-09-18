from app.modules.blacklist.repository import BlacklistRepository
from app.modules.blacklist.seed import DEFAULT_SOURCE_URL, ensure_blacklist_sources_seeded


async def test_seed_adds_default_source_once(blacklist_repository: BlacklistRepository) -> None:
    await ensure_blacklist_sources_seeded(blacklist_repository)
    await ensure_blacklist_sources_seeded(blacklist_repository)

    urls = [s.url for s in await blacklist_repository.list_sources()]
    assert urls.count(DEFAULT_SOURCE_URL) == 1
