from typing import AsyncIterator

import httpx
import pytest
from aiogram import Bot, Dispatcher
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.core.constants import MAX_WEBHOOK_BODY_BYTES
from app.telegram.webhook import TelegramWebhookEndpoint

_SECRET = "s3cret-token"
_PATH = "/telegram"


class _BotProvider(Provider):
    @provide(scope=Scope.APP)
    def bot(self) -> Bot:
        return Bot(token="123456:TEST")


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    TelegramWebhookEndpoint(Dispatcher(), _SECRET).register(app, _PATH)
    container = make_async_container(_BotProvider())
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    await container.close()


async def _oversized_body() -> AsyncIterator[bytes]:
    # chunked, no Content-Length: the stream itself has to be cut off
    chunk = b"x" * 65536
    for _ in range(MAX_WEBHOOK_BODY_BYTES // len(chunk) + 2):
        yield chunk


async def test_rejects_missing_secret_without_reading_body(client: httpx.AsyncClient) -> None:
    response = await client.post(_PATH, content=_oversized_body())
    assert response.status_code == 401


async def test_rejects_wrong_secret(client: httpx.AsyncClient) -> None:
    response = await client.post(
        _PATH, json={"update_id": 1}, headers={"X-Telegram-Bot-Api-Secret-Token": "nope"}
    )
    assert response.status_code == 401


async def test_non_ascii_secret_is_401_not_500(client: httpx.AsyncClient) -> None:
    response = await client.post(
        _PATH,
        json={"update_id": 1},
        headers=[(b"X-Telegram-Bot-Api-Secret-Token", "é".encode())],
    )
    assert response.status_code == 401


async def test_rejects_oversized_body_with_valid_secret(client: httpx.AsyncClient) -> None:
    response = await client.post(
        _PATH, content=_oversized_body(), headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET}
    )
    assert response.status_code == 413


@pytest.mark.filterwarnings("ignore:Detected unknown update type")
async def test_accepts_valid_update(client: httpx.AsyncClient) -> None:
    response = await client.post(
        _PATH, json={"update_id": 1}, headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET}
    )
    assert response.status_code == 200


async def test_rejects_malformed_update(client: httpx.AsyncClient) -> None:
    response = await client.post(
        _PATH, content=b"{not json", headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET}
    )
    assert response.status_code == 422
