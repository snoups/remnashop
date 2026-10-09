import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from dishka import Provider, Scope, make_async_container
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from app.core.constants import USER_KEY
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.promocodes import ValidatePromocodeUseCase
from app.modules.subscriptions import ListOwnActiveSubscriptionsUseCase
from app.telegram.routers.promocode.handlers import (
    _NOTIFICATION_BY_CODE,
    PROMOCODE_INPUT_LIMIT,
    _refusal_key,
    on_promocode_input,
)

_LOCALES_DIR = Path(__file__).parents[4] / "assets" / "translations"


def test_refusal_names_the_specific_reason() -> None:
    expired = ValidationError("expired", code=ErrorCode.PROMOCODE_EXPIRED)
    limit = ValidationError("limit", code=ErrorCode.PROMOCODE_LIMIT_REACHED)
    missing = NotFoundError("missing", code=ErrorCode.PROMOCODE_NOT_FOUND)

    assert _refusal_key(expired) == "ntf-promocode.expired"
    assert _refusal_key(missing) == "ntf-promocode.not-found"
    assert _refusal_key(limit) == "ntf-promocode.not-available"


def test_every_refusal_key_exists_in_each_locale() -> None:
    attributes = {key.split(".", 1)[1] for key in _NOTIFICATION_BY_CODE.values()}
    for menu in _LOCALES_DIR.glob("*/menu.ftl"):
        text = menu.read_text()
        assert all(f"    .{attribute} =" in text for attribute in attributes), menu


class _Runner:
    def get(self, key: str) -> str:
        return key


class _Hub:
    def get_translator_by_locale(self, locale: str) -> _Runner:
        return _Runner()


async def _send_codes(redis: Redis, user_id: int, count: int) -> tuple[AsyncMock, AsyncMock]:
    validate = AsyncMock(side_effect=NotFoundError("missing", code=ErrorCode.PROMOCODE_NOT_FOUND))
    provider = Provider(scope=Scope.APP)
    provider.provide(source=lambda: validate, provides=ValidatePromocodeUseCase)
    provider.provide(source=lambda: AsyncMock(), provides=ListOwnActiveSubscriptionsUseCase)
    provider.provide(source=lambda: _Hub(), provides=TranslatorHub)
    provider.provide(source=lambda: redis, provides=Redis)
    container = make_async_container(provider)
    user = SimpleNamespace(id=user_id, language=SimpleNamespace(value="en"), log="u")
    manager = SimpleNamespace(
        middleware_data={USER_KEY: user, "dishka_container": container},
        dialog_data={},
        show_mode=None,
    )
    answer = AsyncMock()
    message = SimpleNamespace(text="abc", answer=answer)
    for _ in range(count):
        await on_promocode_input(message, None, manager)  # type: ignore[arg-type]
    await container.close()
    return validate, answer


async def test_promocode_input_is_throttled_per_user(redis: Redis) -> None:
    user_id = uuid.uuid4().int % 10**9
    validate, answer = await _send_codes(redis, user_id, PROMOCODE_INPUT_LIMIT + 1)

    assert validate.await_count == PROMOCODE_INPUT_LIMIT
    answer.assert_awaited_with("ntf-promocode.too-many-attempts")

    other, _ = await _send_codes(redis, user_id + 1, 1)
    assert other.await_count == 1
