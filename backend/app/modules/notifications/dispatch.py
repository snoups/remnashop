from typing import Any, Optional, Protocol


class DeliverNotificationDispatch(Protocol):
    async def kiq(
        self,
        *,
        outbox_id: int,
        event_type: str,
        payload: dict[str, Any],
        actor_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> object: ...
