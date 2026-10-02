from typing import Protocol


class RunBackupDispatch(Protocol):
    async def kiq(self, *, kind: str, run_id: int) -> object: ...
