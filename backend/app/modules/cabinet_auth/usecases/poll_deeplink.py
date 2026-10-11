from typing import Optional

from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.auth import IssuedSession
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import DeeplinkStatus
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.users import UserDto


class PollDeeplinkUseCase:
    def __init__(self, store: DeeplinkStore, sign_in: CabinetSignIn) -> None:
        self._store = store
        self._sign_in = sign_in

    async def execute(
        self, binding: str, client_ip: str, user_agent: Optional[str]
    ) -> Optional[tuple[UserDto, IssuedSession]]:
        result = await self._store.take(binding)
        if result.status is DeeplinkStatus.PENDING:
            return None
        if result.profile is None or result.codes is None:
            raise AuthenticationError(
                "The sign-in link has expired", code=ErrorCode.DEEPLINK_EXPIRED
            )
        return await self._sign_in.telegram(result.profile, result.codes, client_ip, user_agent)
