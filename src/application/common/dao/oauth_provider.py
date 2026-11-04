from typing import Protocol, runtime_checkable

from src.application.dto.user import UserOAuthProviderDto
from src.core.enums import OAuthProvider


@runtime_checkable
class UserOAuthProviderDao(Protocol):
    async def create(self, dto: UserOAuthProviderDto) -> UserOAuthProviderDto: ...

    async def delete(self, user_id: int, provider: OAuthProvider) -> bool: ...
