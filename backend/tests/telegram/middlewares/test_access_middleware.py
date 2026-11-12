from typing import Any

from aiogram.types import CallbackQuery, Message
from fluentogram import TranslatorHub

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import AccessMode, Role
from app.modules.settings import AccessSettingsDto, GetAccessSettingsUseCase
from app.modules.users import UserDto
from app.telegram.middlewares.access import AccessMiddleware


class _FakeRunner:
    def get(self, key: str, **kwargs: Any) -> str:
        assert key == "ntf-access.restricted"
        return "Maintenance."


class _FakeHub:
    def get_translator_by_locale(self, locale: str) -> _FakeRunner:
        return _FakeRunner()


class _FakeGetSettings:
    def __init__(self, mode: AccessMode) -> None:
        self._mode = mode

    @property
    def system(self) -> "_FakeGetSettings":
        return self

    async def __call__(self) -> AccessSettingsDto:
        return AccessSettingsDto(mode=self._mode)


class _FakeContainer:
    def __init__(self, mode: AccessMode) -> None:
        self._mode = mode

    async def get(self, dependency_type: type) -> Any:
        if dependency_type is TranslatorHub:
            return _FakeHub()
        assert dependency_type is GetAccessSettingsUseCase
        return _FakeGetSettings(self._mode)


def _fake_message(answered: list[Any]) -> Message:
    async def _answer(text: str, **kwargs: Any) -> None:
        answered.append((text, kwargs))

    message = object.__new__(Message)
    object.__setattr__(message, "successful_payment", None)
    object.__setattr__(message, "answer", _answer)
    return message


async def _run(user: UserDto, mode: AccessMode, answered: list[Any]) -> bool:
    called = False

    async def handler(event: Any, data: dict[str, Any]) -> None:
        nonlocal called
        called = True

    data = {USER_KEY: user, CONTAINER_KEY: _FakeContainer(mode)}
    await AccessMiddleware().middleware_logic(handler, _fake_message(answered), data)
    return called


async def test_restricted_mode_bounces_a_customer() -> None:
    answered: list[Any] = []
    assert await _run(UserDto(name="c"), AccessMode.RESTRICTED, answered) is False
    assert answered == [("Maintenance.", {})]


async def test_restricted_mode_lets_staff_through() -> None:
    answered: list[Any] = []
    assert await _run(UserDto(name="a", role=Role.ADMIN), AccessMode.RESTRICTED, answered) is True
    assert answered == []


async def test_public_mode_passes() -> None:
    assert await _run(UserDto(name="c"), AccessMode.PUBLIC, []) is True


async def test_restricted_mode_answers_a_button_press() -> None:
    answered: list[Any] = []

    async def _answer(text: str, **kwargs: Any) -> None:
        answered.append((text, kwargs))

    callback = object.__new__(CallbackQuery)
    object.__setattr__(callback, "answer", _answer)
    called = False

    async def handler(event: Any, data: dict[str, Any]) -> None:
        nonlocal called
        called = True

    data = {USER_KEY: UserDto(name="c"), CONTAINER_KEY: _FakeContainer(AccessMode.RESTRICTED)}
    await AccessMiddleware().middleware_logic(handler, callback, data)

    assert called is False
    assert answered == [("Maintenance.", {})]


async def test_restricted_mode_lets_a_successful_payment_through() -> None:
    message = _fake_message([])
    object.__setattr__(message, "successful_payment", object())
    called = False

    async def handler(event: Any, data: dict[str, Any]) -> None:
        nonlocal called
        called = True

    data = {USER_KEY: UserDto(name="c"), CONTAINER_KEY: _FakeContainer(AccessMode.RESTRICTED)}
    await AccessMiddleware().middleware_logic(handler, message, data)

    assert called is True
