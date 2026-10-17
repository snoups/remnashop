from typing import Optional, Protocol


class SessionRevoker(Protocol):
    async def revoke_all_by_user(
        self, user_id: int, *, keep_session_id: Optional[int] = None
    ) -> None: ...


class SubscriptionRevoker(Protocol):
    async def revoke_all_by_user(self, user_id: int) -> None: ...


class PasskeyRevoker(Protocol):
    async def delete_all_by_user(self, user_id: int) -> int: ...


class PromocodeLiveness(Protocol):
    async def is_live(self, promocode_id: int) -> bool: ...
