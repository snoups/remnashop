from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.cabinet_auth import DeeplinkStore
from app.modules.identity_links.dto import IdentityClaimDto, IdentityKind, LinkResultDto
from app.modules.identity_links.linker import IdentityLinker
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class TelegramLinkSignInUseCase:
    """The cabinet's side of linking: trades the token from the bot's button for a link."""

    def __init__(
        self,
        settings_repository: SettingsRepository,
        store: DeeplinkStore,
        linker: IdentityLinker,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._store = store
        self._linker = linker
        self._uow = uow

    async def execute(self, user: UserDto, token: str, client_ip: str) -> LinkResultDto:
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
        if not cabinet.telegram_enabled:
            raise AuthenticationError(
                "Telegram sign-in is disabled", code=ErrorCode.CABINET_TELEGRAM_DISABLED
            )
        # a sign-in grant or someone else's link grant never links anything, and
        # isn't used up by the attempt: its own account can still take it
        grant = await self._store.peek_signin(token)
        if grant is None or grant.link_user_id != user.id:
            raise AuthenticationError(
                "The sign-in link has expired", code=ErrorCode.DEEPLINK_EXPIRED
            )
        # taken once: two parallel submissions don't both link
        if await self._store.take_signin(token) is None:
            raise AuthenticationError(
                "The sign-in link has expired", code=ErrorCode.DEEPLINK_EXPIRED
            )
        return await self._linker.link(
            user, IdentityClaimDto(kind=IdentityKind.TELEGRAM, telegram=grant.profile), client_ip
        )
