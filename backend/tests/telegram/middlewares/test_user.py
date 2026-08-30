from typing import Any

from aiogram.enums import ChatType
from aiogram.types import Chat
from aiogram.types import User as AiogramUser

from app.core.config import AppConfig
from app.core.constants import CONFIG_KEY, CONTAINER_KEY, USER_KEY
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import RegisterTelegramUserUseCase
from app.telegram.middlewares.user import UserMiddleware


class _FakeContainer:
    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def get(self, dependency_type: type) -> Any:
        assert dependency_type is RegisterTelegramUserUseCase
        return RegisterTelegramUserUseCase(self._user_repository, self._uow, self._event_publisher)


class _ExplodingContainer:
    async def get(self, dependency_type: type) -> Any:
        raise AssertionError("container should not be queried for non-private-chat events")


def _sender(telegram_id: int = 4242) -> AiogramUser:
    return AiogramUser(id=telegram_id, is_bot=False, first_name="Group Member")


async def _run_middleware(data: dict[str, Any]) -> bool:
    middleware = UserMiddleware()
    handler_called = False

    async def handler(event: Any, handler_data: dict[str, Any]) -> None:
        nonlocal handler_called
        handler_called = True

    await middleware.middleware_logic(handler, object(), data)
    return handler_called


async def test_user_middleware_skips_registration_for_group_chat_messages(
    config: AppConfig,
) -> None:
    data: dict[str, Any] = {
        "event_chat": Chat(id=-100123, type=ChatType.GROUP),
        "event_from_user": _sender(),
        CONTAINER_KEY: _ExplodingContainer(),
        CONFIG_KEY: config,
    }

    handler_called = await _run_middleware(data)

    assert handler_called is True
    assert USER_KEY not in data


async def test_user_middleware_registers_user_for_private_chat_messages(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    data: dict[str, Any] = {
        "event_chat": Chat(id=4242, type=ChatType.PRIVATE),
        "event_from_user": _sender(),
        CONTAINER_KEY: _FakeContainer(user_repository, uow, event_publisher),
        CONFIG_KEY: config,
    }

    handler_called = await _run_middleware(data)

    assert handler_called is True
    assert data[USER_KEY].telegram_id == 4242
    assert await user_repository.get_by_telegram_id(4242) is not None
