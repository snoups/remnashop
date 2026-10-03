from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from httpx import AsyncClient, AsyncHTTPTransport, Timeout
from loguru import logger
from remnapy import RemnawaveSDK

from app.core.config import AppConfig
from app.core.resilient_transport import ResilientTransport


class RemnawaveProvider(Provider):
    scope = Scope.APP

    @provide
    async def get_remnawave(self, config: AppConfig) -> AsyncIterator[RemnawaveSDK]:
        assert config.remnawave.token is not None
        logger.debug("Initializing RemnawaveSDK")

        headers = {}
        headers["Authorization"] = f"Bearer {config.remnawave.token.get_secret_value()}"
        headers["X-Api-Key"] = config.remnawave.caddy_token.get_secret_value()
        headers["CF-Access-Client-Id"] = config.remnawave.cf_client_id.get_secret_value()
        headers["CF-Access-Client-Secret"] = config.remnawave.cf_client_secret.get_secret_value()

        if not config.remnawave.is_external:
            headers["x-forwarded-proto"] = "https"
            headers["x-forwarded-for"] = "127.0.0.1"

        # with transport= given, AsyncClient ignores its own verify/limits/...
        # kwargs, so TLS and pooling go on AsyncHTTPTransport(...)
        transport = ResilientTransport(AsyncHTTPTransport())
        client = AsyncClient(
            base_url=f"{config.remnawave.url.get_secret_value()}/api",
            headers=headers,
            cookies=config.remnawave.cookies,
            timeout=Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
            transport=transport,
        )

        try:
            yield RemnawaveSDK(client)
        finally:
            await client.aclose()
            logger.debug("RemnawaveSDK AsyncClient closed")
