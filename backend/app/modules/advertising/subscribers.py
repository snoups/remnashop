from typing import Final, cast

from app.core.enums import AdLinkChannel
from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.advertising.dispatch import RecordAdLinkAttributionDispatch
from app.modules.advertising.tasks import record_ad_link_attribution_task
from app.modules.users import CabinetUserRegisteredEvent, TelegramUserRegisteredEvent

_record_attribution: Final[RecordAdLinkAttributionDispatch] = cast(
    RecordAdLinkAttributionDispatch, record_ad_link_attribution_task
)


async def _on_telegram_user_registered(
    event: TelegramUserRegisteredEvent, entry: StoredEvent
) -> None:
    if not event.ad_link_code:
        return
    await _record_attribution.kiq(
        user_id=event.user.id,
        ad_link_code=event.ad_link_code,
        channel=AdLinkChannel.BOT.value,
    )


async def _on_cabinet_user_registered(
    event: CabinetUserRegisteredEvent, entry: StoredEvent
) -> None:
    if not event.ad_link_code:
        return
    await _record_attribution.kiq(
        user_id=event.user.id,
        ad_link_code=event.ad_link_code,
        channel=AdLinkChannel.WEBCABINET.value,
    )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(TelegramUserRegisteredEvent, _on_telegram_user_registered)
    bus.subscribe(CabinetUserRegisteredEvent, _on_cabinet_user_registered)
