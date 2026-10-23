from app.modules.cabinet_auth import DeeplinkTicketDto, InviteCodesDto, RequestDeeplinkUseCase
from app.modules.users import UserDto


class RequestTelegramLinkUseCase:
    """The same bot link as sign-in, but its start token remembers who asked to link."""

    def __init__(self, request_deeplink_use_case: RequestDeeplinkUseCase) -> None:
        self._request_deeplink_use_case = request_deeplink_use_case

    async def execute(self, user: UserDto) -> DeeplinkTicketDto:
        return await self._request_deeplink_use_case.execute(InviteCodesDto(), link_user_id=user.id)
