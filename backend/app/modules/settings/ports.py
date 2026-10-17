from typing import Protocol


class OidcIdentityCleaner(Protocol):
    async def delete_all_oidc(self) -> int: ...
