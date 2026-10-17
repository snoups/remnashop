from typing import Optional, Protocol


class SessionRevoker(Protocol):
    async def revoke_all_by_user(
        self, user_id: int, *, keep_session_id: Optional[int] = None
    ) -> None: ...


class SubscriptionRevoker(Protocol):
    async def revoke_all_by_user(self, user_id: int) -> None: ...


class PasskeyRevoker(Protocol):
    async def delete_all_by_user(self, user_id: int) -> int: ...
