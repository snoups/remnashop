from typing import Any

from aiogram.types import CallbackQuery, Message
from fluentogram import TranslatorHub

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.modules.users import UserDto
from app.telegram.middlewares.blacklist import BlacklistMiddleware


class _FakeRunner:
    def get(self, key: str, **kwargs: Any) -> str:
        assert key == "ntf-common.access-restricted"
        return "Access is restricted."


class _FakeTranslatorHub:
    def get_translator_by_locale(self, locale: str) -> _FakeRunner:
        return _FakeRunner()


class _FakeContainer:
    async def get(self, dependency_type: type) -> Any:
        assert dependency_type is TranslatorHub
        return _FakeTranslatorHub()


class _ExplodingContainer:
    async def get(self, dependency_type: type) -> Any:
        raise AssertionError("container should not be queried for a non-blocked user")


def _user(is_blocked: bool) -> UserDto:
    return UserDto(name="Someone", is_blocked=is_blocked)


def _fake_message(answered: list[Any]) -> Message:
    async def _answer(text: str, **kwargs: Any) -> None:
        answered.append((text, kwargs))

    message = object.__new__(Message)
    object.__setattr__(message, "answer", _answer)
    return message


def _fake_callback_query(answered: list[Any]) -> CallbackQuery:
    async def _answer(text: str, **kwargs: Any) -> None:
        answered.append((text, kwargs))

    callback = object.__new__(CallbackQuery)
    object.__setattr__(callback, "answer", _answer)
    return callback


async def _run_middleware(event: Any, data: dict[str, Any]) -> bool:
    middleware = BlacklistMiddleware()
    handler_called = False

    async def handler(event: Any, handler_data: dict[str, Any]) -> None:
        nonlocal handler_called
        handler_called = True

    await middleware.middleware_logic(handler, event, data)
    return handler_called


async def test_blacklist_middleware_bounces_blocked_user_message() -> None:
    answered: list[Any] = []
    message = _fake_message(answered)
    data = {USER_KEY: _user(is_blocked=True), CONTAINER_KEY: _FakeContainer()}

    handler_called = await _run_middleware(message, data)

    assert handler_called is False
    assert answered == [("Access is restricted.", {})]


async def test_blacklist_middleware_bounces_blocked_user_callback_query() -> None:
    answered: list[Any] = []
    callback = _fake_callback_query(answered)
    data = {USER_KEY: _user(is_blocked=True), CONTAINER_KEY: _FakeContainer()}

    handler_called = await _run_middleware(callback, data)

    assert handler_called is False
    assert answered == [("Access is restricted.", {"show_alert": True})]


async def test_blacklist_middleware_passes_through_non_blocked_user() -> None:
    message = _fake_message([])
    data = {USER_KEY: _user(is_blocked=False), CONTAINER_KEY: _ExplodingContainer()}

    handler_called = await _run_middleware(message, data)

    assert handler_called is True


async def test_blacklist_middleware_passes_through_missing_user() -> None:
    message = _fake_message([])
    data: dict[str, Any] = {CONTAINER_KEY: _ExplodingContainer()}

    handler_called = await _run_middleware(message, data)

    assert handler_called is True
