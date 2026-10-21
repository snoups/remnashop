from unittest.mock import AsyncMock, patch

from app.core.enums import Locale, Role
from app.core.event_bus import EventBus
from app.modules.referrals.subscribers import register_subscribers
from app.modules.users import TelegramUserRegisteredEvent, UserDto
from tests.fakes.events import stored_event

_KIQ = "app.modules.referrals.tasks.attach_referral_on_registration_task.kiq"
_USER = UserDto(id=42, login=None, name="u", role=Role.USER, language=Locale.EN)


async def _dispatch(event: TelegramUserRegisteredEvent) -> AsyncMock:
    bus = EventBus()
    register_subscribers(bus)
    with patch(_KIQ, new_callable=AsyncMock) as mock_kiq:
        assert await bus.dispatch_stored(stored_event(event)) is None
    return mock_kiq


async def test_on_user_registered_enqueues_attach_when_code_present() -> None:
    mock_kiq = await _dispatch(TelegramUserRegisteredEvent(user=_USER, referral_code="AB12CD34"))

    mock_kiq.assert_awaited_once_with(user_id=42, referral_code="AB12CD34")


async def test_on_user_registered_skips_when_code_absent() -> None:
    mock_kiq = await _dispatch(TelegramUserRegisteredEvent(user=_USER, ad_link_code="yt"))

    mock_kiq.assert_not_awaited()
