from app.core.enums import OAuthProvider
from app.modules.cabinet_auth import CabinetOAuthAuthorizeUseCase, InviteCodesDto
from app.modules.users import UserDto


class OAuthLinkAuthorizeUseCase:
    def __init__(self, authorize: CabinetOAuthAuthorizeUseCase) -> None:
        self._authorize = authorize

    async def execute(self, user: UserDto, provider: OAuthProvider) -> tuple[str, str]:
        return await self._authorize.execute(provider, InviteCodesDto(), link_user_id=user.id)
