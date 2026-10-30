from typing import Protocol

from app.core.enums import SessionAudience


class OidcIdentityCleaner(Protocol):
    async def delete_all_oidc(self) -> int: ...


class AudienceSessionRevoker(Protocol):
    async def revoke_all_by_audience(self, audience: SessionAudience) -> None: ...
