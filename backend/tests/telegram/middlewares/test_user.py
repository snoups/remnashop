from typing import Any, Optional

from aiogram.enums import ChatType
from aiogram.types import Chat, Message
from aiogram.types import User as AiogramUser
from fluentogram import TranslatorHub
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.models.user_registration import UserRegistration
from app.core.db.uow import UnitOfWork
from app.core.enums import AccessMode, Locale, RegistrationSource
from app.core.ports import EventPublisher
from app.modules.access import CheckRegistrationAccessUseCase
from app.modules.advertising.repository import AdLinkRepository
from app.modules.blacklist import BlacklistRepository
from app.modules.cabinet_auth import DeeplinkStore, InviteCodesDto
from app.modules.settings import GetAccessSettingsUseCase, SettingsRepository
from app.modules.settings.dto import UpdateAccessSettingsDto
from app.modules.users import CreateUserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import FindTelegramUserUseCase, RegisterTelegramUserUseCase
from app.telegram.middlewares.user import UserMiddleware


class _FakeRunner:
    def get(self, key: str, **kwargs: Any) -> str:
        return key


class _FakeHub:
    translators_map = {"en": [], "ru": []}
    root_locale = "en"

    def get_translator_by_locale(self, locale: str) -> _FakeRunner:
        return _FakeRunner()


class _FakeContainer:
    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        settings_repository: SettingsRepository,
        ad_link_repository: AdLinkRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        deeplink_store: Optional[DeeplinkStore] = None,
    ) -> None:
        self._deeplink_store = deeplink_store
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._settings_repository = settings_repository
        self._ad_link_repository = ad_link_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def get(self, dependency_type: type) -> Any:
        if dependency_type is TranslatorHub:
            return _FakeHub()
        if dependency_type is DeeplinkStore:
            return self._deeplink_store
        if dependency_type is CheckRegistrationAccessUseCase:
            return CheckRegistrationAccessUseCase(
                GetAccessSettingsUseCase(self._settings_repository, self._uow),
                self._user_repository,
                self._ad_link_repository,
                self._uow,
            )
        if dependency_type is FindTelegramUserUseCase:
            return FindTelegramUserUseCase(self._user_repository, self._uow)
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


async def test_user_middleware_skips_registration_for_group_chat_messages() -> None:
    data: dict[str, Any] = {
        "event_chat": Chat(id=-100123, type=ChatType.GROUP),
        "event_from_user": _sender(),
        CONTAINER_KEY: _ExplodingContainer(),
    }

    handler_called = await _run_middleware(data)

    assert handler_called is True
    assert USER_KEY not in data


async def test_user_middleware_registers_user_for_private_chat_messages(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    data: dict[str, Any] = {
        "event_chat": Chat(id=4242, type=ChatType.PRIVATE),
        "event_from_user": _sender(),
        CONTAINER_KEY: _FakeContainer(
            user_repository,
            blacklist_repository,
            settings_repository,
            ad_link_repository,
            uow,
            event_publisher,
        ),
    }

    handler_called = await _run_middleware(data)

    assert handler_called is True
    assert data[USER_KEY].telegram_id == 4242
    assert await user_repository.find_by_telegram_id(4242) is not None


async def test_user_middleware_carries_ad_link_code_from_start_payload(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    message = Message.model_construct(
        message_id=1,
        date=0,
        chat=Chat(id=5252, type=ChatType.PRIVATE),
        text="/start ad_middleware-code",
        from_user=AiogramUser(
            id=5252, is_bot=False, first_name="A", is_premium=True, language_code="pt-br"
        ),
    )
    data: dict[str, Any] = {
        "event_chat": message.chat,
        "event_from_user": message.from_user,
        CONTAINER_KEY: _FakeContainer(
            user_repository,
            blacklist_repository,
            settings_repository,
            ad_link_repository,
            uow,
            event_publisher,
        ),
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
    registration = await session.get(UserRegistration, rows[0].payload["user"]["id"])
    assert registration is not None
    assert registration.source is RegistrationSource.BOT
    assert registration.start_payload == "ad_middleware-code"
    assert registration.telegram_is_premium is True
    assert registration.telegram_language_code == "pt-br"


async def test_user_middleware_syncs_username_and_an_active_telegram_language(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    container = _FakeContainer(
        user_repository,
        blacklist_repository,
        settings_repository,
        ad_link_repository,
        uow,
        event_publisher,
    )

    async def run(sender: AiogramUser) -> Any:
        data: dict[str, Any] = {
            "event_chat": Chat(id=sender.id, type=ChatType.PRIVATE),
            "event_from_user": sender,
            CONTAINER_KEY: container,
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


def _start_message(telegram_id: int, text: str, answered: list[Any]) -> Message:
    async def _answer(text: str, **kwargs: Any) -> None:
        answered.append((text, kwargs))

    message = Message.model_construct(
        message_id=1,
        date=0,
        chat=Chat(id=telegram_id, type=ChatType.PRIVATE),
        text=text,
        from_user=_sender(telegram_id),
    )
    object.__setattr__(message, "answer", _answer)
    return message


async def _run_start(
    text: str,
    telegram_id: int,
    container: _FakeContainer,
    answered: list[Any],
) -> bool:
    message = _start_message(telegram_id, text, answered)
    data: dict[str, Any] = {
        "event_chat": message.chat,
        "event_from_user": message.from_user,
        CONTAINER_KEY: container,
    }
    middleware = UserMiddleware()
    handler_called = False

    async def handler(event: Any, handler_data: dict[str, Any]) -> None:
        nonlocal handler_called
        handler_called = True

    await middleware.middleware_logic(handler, message, data)
    return handler_called


async def test_invite_only_refuses_an_uninvited_newcomer_without_creating_them(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(mode=AccessMode.INVITED)
        )
        await uow.commit()
    container = _FakeContainer(
        user_repository,
        blacklist_repository,
        settings_repository,
        ad_link_repository,
        uow,
        event_publisher,
    )
    answered: list[Any] = []

    handler_called = await _run_start("/start", 6161, container, answered)

    assert handler_called is False
    assert answered and answered[0][0] == "ntf-access.invite-only"
    assert await user_repository.find_by_telegram_id(6161) is None


async def test_invite_only_registers_a_newcomer_with_a_referral_code(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    async with uow:
        referrer = await user_repository.create(CreateUserDto(name="ref", telegram_id=6262))
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(mode=AccessMode.INVITED)
        )
        await uow.commit()
    container = _FakeContainer(
        user_repository,
        blacklist_repository,
        settings_repository,
        ad_link_repository,
        uow,
        event_publisher,
    )

    handler_called = await _run_start(f"/start ref_{referrer.referral_code}", 6363, container, [])

    assert handler_called is True
    assert await user_repository.find_by_telegram_id(6363) is not None


async def test_webauth_start_registers_a_newcomer_with_the_cabinet_invite(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
    redis: Redis,
) -> None:
    store = DeeplinkStore(redis)
    token = await store.create(InviteCodesDto(referral_code="abc"))
    container = _FakeContainer(
        user_repository,
        blacklist_repository,
        settings_repository,
        ad_link_repository,
        uow,
        event_publisher,
        store,
    )

    await _run_start(f"/start webauth_{token}", 6464, container, [])

    rows = (
        await session.scalars(
            select(EventOutboxEntry).where(
                EventOutboxEntry.event_type == "CabinetUserRegisteredEvent"
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["referral_code"] == "abc"


async def _run_link_start(
    telegram_id: int, container: _FakeContainer, token: str
) -> dict[str, Any]:
    message = _start_message(telegram_id, f"/start webauth_{token}", [])
    data: dict[str, Any] = {
        "event_chat": message.chat,
        "event_from_user": message.from_user,
        CONTAINER_KEY: container,
    }
    seen: dict[str, Any] = {}

    async def handler(event: Any, handler_data: dict[str, Any]) -> None:
        seen.update(handler_data)

    await UserMiddleware().middleware_logic(handler, message, data)
    return seen


async def test_link_start_skips_registration(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    async with uow:
        owner = await user_repository.create(CreateUserDto(name="owner", email="o@gmail.com"))
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(mode=AccessMode.INVITED)
        )
        await uow.commit()
    store = DeeplinkStore(redis)
    token = await store.create(InviteCodesDto(), link_user_id=owner.id)
    container = _FakeContainer(
        user_repository,
        blacklist_repository,
        settings_repository,
        ad_link_repository,
        uow,
        event_publisher,
        store,
    )

    seen = await _run_link_start(6565, container, token)

    assert seen and seen.get(USER_KEY) is None
    assert await user_repository.find_by_telegram_id(6565) is None
    # peeking only: the bot still has the start token to spend
    assert await store.peek(token) is not None


async def test_link_start_existing_user_loaded(
    user_repository: UserRepository,
    blacklist_repository: BlacklistRepository,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
    redis: Redis,
) -> None:
    async with uow:
        existing = await user_repository.create(CreateUserDto(name="tg", telegram_id=6666))
        owner = await user_repository.create(CreateUserDto(name="owner", email="o@gmail.com"))
        await uow.commit()
    store = DeeplinkStore(redis)
    token = await store.create(InviteCodesDto(), link_user_id=owner.id)
    container = _FakeContainer(
        user_repository,
        blacklist_repository,
        settings_repository,
        ad_link_repository,
        uow,
        event_publisher,
        store,
    )
    before = len((await session.scalars(select(EventOutboxEntry))).all())

    seen = await _run_link_start(6666, container, token)

    assert seen[USER_KEY].id == existing.id
    assert len((await session.scalars(select(EventOutboxEntry))).all()) == before
