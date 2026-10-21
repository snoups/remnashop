import pytest
from aiogram.client.session.aiohttp import AiohttpSession

from app.modules.settings.usecases.set_bot_proxy import _PROXY_SCHEMES, normalize_proxy_url


@pytest.mark.parametrize("scheme", sorted(_PROXY_SCHEMES))
async def test_every_accepted_scheme_opens_a_bot_session(scheme: str) -> None:
    # an accepted URL a session can't parse would crash the bot process on startup
    proxy = normalize_proxy_url(f"{scheme}://user:pass@proxy.example:1080")

    session = AiohttpSession(proxy=proxy)
    await session.create_session()
    await session.close()
