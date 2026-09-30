from unittest.mock import AsyncMock, patch

from app.core.events import EventCategory, StoredEvent
from app.core.utils.time import datetime_now
from app.modules.referrals.events import _on_telegram_user_registered

_KIQ = "app.modules.referrals.tasks.attach_referral_on_registration_task.kiq"


def _entry(payload: dict) -> StoredEvent:
    return StoredEvent(
        outbox_id=1,
        category=EventCategory.USER,
        event_type="TelegramUserRegisteredEvent",
        occurred_at=datetime_now(),
        payload=payload,
        actor_id=None,
        actor_login=None,
        actor_name=None,
        actor_email=None,
        ip_address=None,
    )


async def test_on_telegram_user_registered_enqueues_attach_when_code_present() -> None:
    entry = _entry({"user": {"id": 42}, "referral_code": "AB12CD34"})

    with patch(_KIQ, new_callable=AsyncMock) as mock_kiq:
        await _on_telegram_user_registered(entry)

    mock_kiq.assert_awaited_once_with(user_id=42, referral_code="AB12CD34")


async def test_on_telegram_user_registered_skips_when_code_absent() -> None:
    with patch(_KIQ, new_callable=AsyncMock) as mock_kiq:
        await _on_telegram_user_registered(_entry({"user": {"id": 42}, "ad_link_code": "yt"}))

    mock_kiq.assert_not_awaited()
