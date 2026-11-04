from typing import Protocol, runtime_checkable


@runtime_checkable
class WebhookDao(Protocol):
    async def is_hash_exists(self, bot_id: int, webhook_hash: str) -> bool: ...

    async def save_hash(self, bot_id: int, webhook_hash: str) -> None: ...

    async def clear_all_hashes(self, bot_id: int) -> None: ...
