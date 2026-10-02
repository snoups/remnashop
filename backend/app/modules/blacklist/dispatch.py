from typing import Protocol


class SyncBlacklistSourcesDispatch(Protocol):
    async def kiq(self) -> object: ...


class ReconcileBlacklistDispatch(Protocol):
    async def kiq(self) -> object: ...
