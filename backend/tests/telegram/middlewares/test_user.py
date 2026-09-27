from types import SimpleNamespace
from typing import Any

from aiogram.enums import ChatType
from aiogram.types import Chat, Message
from aiogram.types import User as AiogramUser
from fluentogram import TranslatorHub
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import CONFIG_KEY, CONTAINER_KEY, USER_KEY
from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.ports import EventPublisher
from app.modules.blacklist import BlacklistRepository
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import RegisterTelegramUserUseCase
from app.telegram.middlewares.user import UserMiddleware


class _FakeContainer:
    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def get(self, dependency_type: type) -> Any:
        if dependency_type is TranslatorHub:
            return SimpleNamespace(translators_map={"en": [], "ru": []})
        assert dependency_type is RegisterTelegramUserUseCase
        return RegisterTelegramUserUseCase(
            self._user_repository, self._blacklist_repository, self._uow, self._event_publisher
        )


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
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    data: dict[str, Any] = {
        "event_chat": Chat(id=4242, type=ChatType.PRIVATE),
        "event_from_user": _sender(),
        CONTAINER_KEY: _FakeContainer(user_repository, blacklist_repository, uow, event_publisher),
        CONFIG_KEY: config,
    }

    handler_called = await _run_middleware(data)

    assert handler_called is True
    assert data[USER_KEY].telegram_id == 4242
    assert await user_repository.get_by_telegram_id(4242) is not None


async def test_user_middleware_carries_ad_link_code_from_start_payload(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
    session: AsyncSession,
) -> None:
    message = Message.model_construct(
        message_id=1,
        date=0,
        chat=Chat(id=5252, type=ChatType.PRIVATE),
        text="/start ad_middleware-code",
        from_user=_sender(5252),
    )
    data: dict[str, Any] = {
        "event_chat": message.chat,
        "event_from_user": message.from_user,
        CONTAINER_KEY: _FakeContainer(user_repository, blacklist_repository, uow, event_publisher),
        CONFIG_KEY: config,
    }

    middleware = UserMiddleware()

    async def handler(event: Any, handler_data: dict[str, Any]) -> None:
        return None

    await middleware.middleware_logic(handler, message, data)

    rows = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "TelegramUserRegisteredEvent"
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["ad_link_code"] == "middleware-code"


async def test_user_middleware_syncs_username_and_an_active_telegram_language(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    config: AppConfig,
) -> None:
    container = _FakeContainer(user_repository, blacklist_repository, uow, event_publisher)

    async def run(sender: AiogramUser) -> Any:
        data: dict[str, Any] = {
            "event_chat": Chat(id=sender.id, type=ChatType.PRIVATE),
            "event_from_user": sender,
            CONTAINER_KEY: container,
            CONFIG_KEY: config,
        }
        await _run_middleware(data)
        return data[USER_KEY]

    base = {"id": 6262, "is_bot": False, "first_name": "Ann"}
    created = await run(AiogramUser(**base, username="ann", language_code="ru"))
    assert created.username == "ann" and created.language == Locale.RU

    # an inactive Telegram language keeps the stored one
    kept = await run(AiogramUser(**base, username="ann2", language_code="de"))
    assert kept.username == "ann2" and kept.language == Locale.RU

    switched = await run(AiogramUser(**base, username="ann2", language_code="en-US"))
    assert switched.language == Locale.EN
