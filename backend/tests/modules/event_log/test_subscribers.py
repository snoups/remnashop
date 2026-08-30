from unittest.mock import AsyncMock, patch

from app.core.enums import Locale, Role
from app.core.event_bus import EventBus
from app.modules.auth.events import LoginSucceededEvent
from app.modules.event_log.subscribers import register_subscribers
from app.modules.users.dto import UserDto
from app.modules.users.events import AdminCreatedEvent

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
ADMIN = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)


async def test_register_subscribers_persists_every_event_via_kiq() -> None:
    bus = EventBus()
    register_subscribers(bus)

    with patch("app.modules.event_log.subscribers.persist_event_task") as mock_task:
        mock_task.kiq = AsyncMock()
        await bus.publish(AdminCreatedEvent(actor=OWNER, target=ADMIN))
        await bus.shutdown()

        mock_task.kiq.assert_awaited_once()
        call_kwargs = mock_task.kiq.await_args.kwargs
        assert call_kwargs["event_type"] == "AdminCreatedEvent"
        assert call_kwargs["category"] == "ADMIN_MANAGEMENT"
        assert call_kwargs["actor_id"] == OWNER.id
        assert call_kwargs["actor_login"] == OWNER.login
        assert "password_hash" not in str(call_kwargs["payload"])


async def test_register_subscribers_persists_user_event_actor() -> None:
    bus = EventBus()
    register_subscribers(bus)

    with patch("app.modules.event_log.subscribers.persist_event_task") as mock_task:
        mock_task.kiq = AsyncMock()
        await bus.publish(LoginSucceededEvent(user=OWNER))
        await bus.shutdown()

        mock_task.kiq.assert_awaited_once()
        call_kwargs = mock_task.kiq.await_args.kwargs
        assert call_kwargs["event_type"] == "LoginSucceededEvent"
        assert call_kwargs["category"] == "AUTH"
        assert call_kwargs["actor_id"] == OWNER.id
        assert call_kwargs["actor_login"] == OWNER.login


async def test_register_subscribers_drops_api_token_actor_id() -> None:
    bus = EventBus()
    register_subscribers(bus)
    api_token_actor = UserDto(
        id=0, name="API Token: ci", role=Role.USER, language=Locale.EN, is_api_token=True
    )

    with patch("app.modules.event_log.subscribers.persist_event_task") as mock_task:
        mock_task.kiq = AsyncMock()
        await bus.publish(AdminCreatedEvent(actor=api_token_actor, target=ADMIN))
        await bus.shutdown()

        mock_task.kiq.assert_awaited_once()
        call_kwargs = mock_task.kiq.await_args.kwargs
        assert call_kwargs["actor_id"] is None
        assert call_kwargs["actor_name"] == "API Token: ci"


async def test_register_subscribers_drops_system_actor_id() -> None:
    bus = EventBus()
    register_subscribers(bus)
    system_actor = UserDto(id=-1, name="SYSTEM", role=Role.SYSTEM, language=Locale.EN)

    with patch("app.modules.event_log.subscribers.persist_event_task") as mock_task:
        mock_task.kiq = AsyncMock()
        await bus.publish(AdminCreatedEvent(actor=system_actor, target=ADMIN))
        await bus.shutdown()

        mock_task.kiq.assert_awaited_once()
        call_kwargs = mock_task.kiq.await_args.kwargs
        assert call_kwargs["actor_id"] is None
        assert call_kwargs["actor_name"] == "SYSTEM"
