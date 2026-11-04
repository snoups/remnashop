from collections.abc import Iterable
from typing import Optional, Protocol

from app.core.enums import OAuthProvider


class SessionRevoker(Protocol):
    async def revoke_all_by_user(
        self, user_id: int, *, keep_session_id: Optional[int] = None
    ) -> None: ...


class SubscriptionRevoker(Protocol):
    async def revoke_all_by_user(self, user_id: int) -> None: ...


class PasskeyRevoker(Protocol):
    async def delete_all_by_user(self, user_id: int) -> int: ...


class OAuthIdentityLookup(Protocol):
    async def user_ids_with_identities(
        self, user_ids: list[int], providers: Iterable[OAuthProvider]
    ) -> set[int]: ...


class PromocodeLiveness(Protocol):
    async def is_live(self, promocode_id: int) -> bool: ...
