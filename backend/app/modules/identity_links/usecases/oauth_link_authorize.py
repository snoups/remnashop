from app.core.enums import OAuthProvider
from app.modules.cabinet_auth import CabinetOAuthAuthorizeUseCase, InviteCodesDto
from app.modules.users import UserDto


class OAuthLinkAuthorizeUseCase:
    def __init__(self, cabinet_oauth_authorize_use_case: CabinetOAuthAuthorizeUseCase) -> None:
        self._cabinet_oauth_authorize_use_case = cabinet_oauth_authorize_use_case

    async def execute(self, user: UserDto, provider: OAuthProvider) -> tuple[str, str]:
        return await self._cabinet_oauth_authorize_use_case.execute(
            provider, InviteCodesDto(), link_user_id=user.id
        )
