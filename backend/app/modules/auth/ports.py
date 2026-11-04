from typing import Protocol


class PasskeyCounter(Protocol):
    async def count_by_user(self, user_id: int) -> int: ...
