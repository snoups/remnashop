from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import PermissionDeniedError
from app.modules.cabinet_auth import CabinetOAuthAuthorizeUseCase, InviteCodesDto
from app.modules.identity_links.dto import can_edit_identity, identity_kind_for
from app.modules.users import UserDto


class OAuthLinkAuthorizeUseCase:
    def __init__(self, cabinet_oauth_authorize_use_case: CabinetOAuthAuthorizeUseCase) -> None:
        self._cabinet_oauth_authorize_use_case = cabinet_oauth_authorize_use_case

    async def execute(self, user: UserDto, provider: OAuthProvider) -> tuple[str, str]:
        if not can_edit_identity(user, identity_kind_for(provider)):
            raise PermissionDeniedError(
                "Staff change this sign-in method in the dashboard",
                code=ErrorCode.PERMISSION_DENIED,
            )
        return await self._cabinet_oauth_authorize_use_case.execute(
            provider, InviteCodesDto(), link_user_id=user.id
        )
