from unittest.mock import AsyncMock, patch

from app.core.enums import AdLinkChannel
from app.core.events import EventCategory, StoredEvent
from app.core.utils.time import datetime_now
from app.modules.advertising.subscribers import (
    _on_cabinet_user_registered,
    _on_telegram_user_registered,
)


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


async def test_on_telegram_user_registered_enqueues_task_when_code_present() -> None:
    entry = _entry({"user": {"id": 42}, "ad_link_code": "yt-jan"})

    with patch(
        "app.modules.advertising.subscribers.record_ad_link_attribution_task.kiq",
        new_callable=AsyncMock,
    ) as mock_kiq:
        await _on_telegram_user_registered(entry)

    mock_kiq.assert_awaited_once_with(
        user_id=42, ad_link_code="yt-jan", channel=AdLinkChannel.BOT.value
    )


async def test_on_telegram_user_registered_skips_when_code_absent() -> None:
    entry = _entry({"user": {"id": 42}, "ad_link_code": None})

    with patch(
        "app.modules.advertising.subscribers.record_ad_link_attribution_task.kiq",
        new_callable=AsyncMock,
    ) as mock_kiq:
        await _on_telegram_user_registered(entry)

    mock_kiq.assert_not_awaited()


async def test_on_cabinet_user_registered_attributes_to_webcabinet() -> None:
    entry = _entry({"user": {"id": 42}, "ad_link_code": "yt-jan", "method": "EMAIL"})

    with patch(
        "app.modules.advertising.subscribers.record_ad_link_attribution_task.kiq",
        new_callable=AsyncMock,
    ) as mock_kiq:
        await _on_cabinet_user_registered(entry)

    mock_kiq.assert_awaited_once_with(
        user_id=42, ad_link_code="yt-jan", channel=AdLinkChannel.WEBCABINET.value
    )
