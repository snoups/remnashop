from types import SimpleNamespace
from typing import Any

from app.core.constants import CONTAINER_KEY
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import GetBotCommandsUseCase
from app.telegram.middlewares.command_gate import CommandGateMiddleware


class _FakeContainer:
    def __init__(self, settings_repository: SettingsRepository) -> None:
        self._settings_repository = settings_repository

    async def get(self, dependency_type: type) -> Any:
        assert dependency_type is GetBotCommandsUseCase
        return GetBotCommandsUseCase(self._settings_repository)


class _ExplodingContainer:
    async def get(self, dependency_type: type) -> Any:
        raise AssertionError("container should not be queried for non-command messages")


async def _run_middleware(message: Any, data: dict[str, Any]) -> bool:
    middleware = CommandGateMiddleware()
    handler_called = False

    async def handler(event: Any, handler_data: dict[str, Any]) -> None:
        nonlocal handler_called
        handler_called = True

    await middleware.middleware_logic(handler, message, data)
    return handler_called


async def test_command_gate_blocks_disabled_command(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.replace_bot_commands([("menu", False)])
    message = SimpleNamespace(text="/menu")

    handler_called = await _run_middleware(
        message, {CONTAINER_KEY: _FakeContainer(settings_repository)}
    )

    assert handler_called is False


async def test_command_gate_allows_enabled_command(
    settings_repository: SettingsRepository,
) -> None:
    message = SimpleNamespace(text="/menu")

    handler_called = await _run_middleware(
        message, {CONTAINER_KEY: _FakeContainer(settings_repository)}
    )

    assert handler_called is True


async def test_command_gate_ignores_non_command_messages() -> None:
    message = SimpleNamespace(text="hello there")

    handler_called = await _run_middleware(message, {CONTAINER_KEY: _ExplodingContainer()})

    assert handler_called is True


async def test_command_gate_passes_through_commands_outside_registry() -> None:
    message = SimpleNamespace(text="/start")

    handler_called = await _run_middleware(message, {CONTAINER_KEY: _ExplodingContainer()})

    assert handler_called is True
