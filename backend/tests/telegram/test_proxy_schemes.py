import httpx
import pytest
from aiogram.client.session.aiohttp import AiohttpSession

from app.modules.settings.usecases.set_bot_proxy import _PROXY_SCHEMES, normalize_proxy_url


@pytest.mark.parametrize("scheme", sorted(_PROXY_SCHEMES))
async def test_every_accepted_scheme_works_in_both_clients(scheme: str) -> None:
    # an accepted URL the bot process can't parse would crash it on startup
    proxy = normalize_proxy_url(f"{scheme}://user:pass@proxy.example:1080")

    session = AiohttpSession(proxy=proxy)
    await session.create_session()
    await session.close()
    async with httpx.AsyncClient(proxy=proxy):
        pass
