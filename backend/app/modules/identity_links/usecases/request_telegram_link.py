from app.modules.cabinet_auth import DeeplinkTicketDto, InviteCodesDto, RequestDeeplinkUseCase
from app.modules.users import UserDto


class RequestTelegramLinkUseCase:
    """The same bot link as sign-in, but its start token remembers who asked to link."""

    def __init__(self, request_deeplink: RequestDeeplinkUseCase) -> None:
        self._request_deeplink = request_deeplink

    async def execute(self, user: UserDto) -> DeeplinkTicketDto:
        return await self._request_deeplink.execute(InviteCodesDto(), link_user_id=user.id)
