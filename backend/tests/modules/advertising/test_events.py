from unittest.mock import AsyncMock, patch

from app.core.enums import AdLinkChannel, CabinetSignInMethod, Locale, Role
from app.core.event_bus import EventBus
from app.core.events import BaseEvent
from app.modules.advertising.subscribers import register_subscribers
from app.modules.users import CabinetUserRegisteredEvent, TelegramUserRegisteredEvent, UserDto
from tests.fakes.events import stored_event

_KIQ = "app.modules.advertising.subscribers.record_ad_link_attribution_task.kiq"
_USER = UserDto(id=42, login=None, name="u", role=Role.USER, language=Locale.EN)


async def _dispatch(event: BaseEvent) -> AsyncMock:
    bus = EventBus()
    register_subscribers(bus)
    with patch(_KIQ, new_callable=AsyncMock) as mock_kiq:
        assert await bus.dispatch_stored(stored_event(event)) is None
    return mock_kiq


async def test_on_telegram_user_registered_enqueues_task_when_code_present() -> None:
    mock_kiq = await _dispatch(TelegramUserRegisteredEvent(user=_USER, ad_link_code="yt-jan"))

    mock_kiq.assert_awaited_once_with(
        user_id=42, ad_link_code="yt-jan", channel=AdLinkChannel.BOT.value
    )


async def test_on_telegram_user_registered_skips_when_code_absent() -> None:
    mock_kiq = await _dispatch(TelegramUserRegisteredEvent(user=_USER, ad_link_code=None))

    mock_kiq.assert_not_awaited()


async def test_on_cabinet_user_registered_attributes_to_webcabinet() -> None:
    mock_kiq = await _dispatch(
        CabinetUserRegisteredEvent(
            user=_USER, method=CabinetSignInMethod.EMAIL, ad_link_code="yt-jan"
        )
    )

    mock_kiq.assert_awaited_once_with(
        user_id=42, ad_link_code="yt-jan", channel=AdLinkChannel.WEBCABINET.value
    )
