from app.core.enums import AdLinkChannel
from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.advertising.tasks import record_ad_link_attribution_task
from app.modules.users import CabinetUserRegisteredEvent, TelegramUserRegisteredEvent


async def _on_telegram_user_registered(entry: StoredEvent) -> None:
    ad_link_code = entry.payload.get("ad_link_code")
    if not ad_link_code:
        return
    await record_ad_link_attribution_task.kiq(  # type: ignore[call-overload]
        user_id=entry.payload["user"]["id"],
        ad_link_code=ad_link_code,
        channel=AdLinkChannel.BOT.value,
    )


async def _on_cabinet_user_registered(entry: StoredEvent) -> None:
    ad_link_code = entry.payload.get("ad_link_code")
    if not ad_link_code:
        return
    await record_ad_link_attribution_task.kiq(  # type: ignore[call-overload]
        user_id=entry.payload["user"]["id"],
        ad_link_code=ad_link_code,
        channel=AdLinkChannel.WEBCABINET.value,
    )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(TelegramUserRegisteredEvent, _on_telegram_user_registered)
    bus.subscribe(CabinetUserRegisteredEvent, _on_cabinet_user_registered)
