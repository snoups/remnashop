from typing import Protocol


class StartBroadcastDispatch(Protocol):
    async def kiq(self, *, broadcast_id: int) -> object: ...


class DeliverBroadcastDispatch(Protocol):
    async def kiq(self, *, broadcast_id: int) -> object: ...


class RecallBroadcastDispatch(Protocol):
    async def kiq(self, *, broadcast_id: int) -> object: ...
