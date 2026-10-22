from typing import Callable

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetMe
from aiogram.types import ChatMemberAdministrator, ChatMemberMember, ChatMemberOwner
from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.modules.settings import telegram_status
from app.modules.settings.dto import UpdateBotRequirementsDto, UpdateBotSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import UpdateBotRequirementsUseCase
from app.modules.users.dto import UserDto
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot

_OWNER = UserDto(id=1, name="owner", role=Role.OWNER)


@pytest.fixture(autouse=True)
async def _seed_owner_row(session: AsyncSession) -> None:
    # event_outbox.actor_id is a real FK
    session.add(
        User(
            id=1,
            name="owner",
            telegram_id=1,
            role=Role.OWNER,
            language=Locale.EN,
            is_blocked=False,
        )
    )
    await session.flush()


def _requirements(**overrides: object) -> UpdateBotRequirementsDto:
    values: dict[str, object] = {
        "channel_required": False,
        "channel_id": None,
        "channel_url": None,
    }
    values.update(overrides)
    return UpdateBotRequirementsDto(**values)  # type: ignore[arg-type]


@pytest.fixture
def use_case(
    settings_repository: SettingsRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> UpdateBotRequirementsUseCase:
    return UpdateBotRequirementsUseCase(settings_repository, uow, event_publisher)


@pytest.fixture
async def _configured_bot(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_bot_settings(
            UpdateBotSettingsDto(token="123:abc", secret_token="s")
        )


async def test_channel_required_without_id_is_rejected(
    use_case: UpdateBotRequirementsUseCase,
) -> None:
    with pytest.raises(ValidationError) as error:
        await use_case(_OWNER, _requirements(channel_required=True, channel_url="https://t.me/x"))
    assert error.value.code is ErrorCode.BOT_REQUIREMENTS_INCOMPLETE


async def test_channel_the_bot_cannot_see_is_rejected(
    use_case: UpdateBotRequirementsUseCase,
    _configured_bot: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _not_admin(token: str, proxy: object, channel_id: int) -> bool:
        return False

    monkeypatch.setattr(
        "app.modules.settings.usecases.update_bot_requirements.is_bot_channel_admin", _not_admin
    )
    with pytest.raises(ValidationError) as error:
        await use_case(
            _OWNER,
            _requirements(channel_required=True, channel_id=-100, channel_url="https://t.me/x"),
        )
    assert error.value.code is ErrorCode.CHANNEL_NOT_ACCESSIBLE


async def test_channel_check_without_a_bot_is_rejected(
    use_case: UpdateBotRequirementsUseCase,
) -> None:
    with pytest.raises(ValidationError) as error:
        await use_case(
            _OWNER,
            _requirements(channel_required=True, channel_id=-100, channel_url="https://t.me/x"),
        )
    assert error.value.code is ErrorCode.CHANNEL_NOT_ACCESSIBLE


async def test_valid_requirements_are_saved(
    use_case: UpdateBotRequirementsUseCase,
    _configured_bot: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _admin(token: str, proxy: object, channel_id: int) -> bool:
        return True

    monkeypatch.setattr(
        "app.modules.settings.usecases.update_bot_requirements.is_bot_channel_admin", _admin
    )
    saved = await use_case(
        _OWNER,
        _requirements(
            channel_required=True,
            channel_id=-100,
            channel_url="https://t.me/x",
        ),
    )
    assert saved.channel_required and saved.channel_id == -100


async def test_only_values_that_differ_are_recorded_as_changed(
    use_case: UpdateBotRequirementsUseCase, session: AsyncSession
) -> None:
    await use_case(_OWNER, _requirements(channel_url="https://t.me/a"))

    await use_case(_OWNER, _requirements(channel_url="https://t.me/b"))

    rows = (await session.scalars(select(EventOutboxEntry).order_by(EventOutboxEntry.id))).all()
    assert rows[-1].payload["changed_fields"] == ["channel_url"]


def _member(status: str) -> object:
    user = TelegramUser(id=123, is_bot=True, first_name="bot")
    if status == "administrator":
        return ChatMemberAdministrator(
            user=user,
            can_be_edited=False,
            is_anonymous=False,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=False,
            can_change_info=True,
            can_invite_users=True,
            can_post_stories=False,
            can_edit_stories=False,
            can_delete_stories=False,
            can_send_welcome_messages=False,
        )
    if status == "creator":
        return ChatMemberOwner(user=user, is_anonymous=False)
    return ChatMemberMember(user=user)


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (lambda: _member("administrator"), True),
        (lambda: _member("creator"), True),
        (lambda: _member("member"), False),
        (lambda: TelegramBadRequest(method=GetMe(), message="chat not found"), False),
    ],
    ids=["administrator", "creator", "member", "chat-not-found"],
)
async def test_is_bot_channel_admin(
    monkeypatch: pytest.MonkeyPatch, reply: Callable[[], object], expected: bool
) -> None:
    session = use_fake_bot(monkeypatch, FakeBotSession({"GetChatMember": reply()}))

    assert await telegram_status.is_bot_channel_admin("123:abc", None, -100) is expected
    [call] = session.called("GetChatMember")
    assert (call.chat_id, call.user_id) == (-100, 123)
