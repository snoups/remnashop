from typing import Final, Optional

from app.core.config import AppConfig
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import BotSignInGrantDto, TelegramProfileDto

# a fragment, not a query: it never reaches a proxy log or a Referer
_SIGNIN_PATH: Final[str] = "/login/bot#token="
_LINK_PATH: Final[str] = "/link/bot#token="


class IssueBotSignInLinkUseCase:
    """The bot's side: spends the cabinet's start link, hands back a one-time sign-in URL."""

    def __init__(self, store: DeeplinkStore, config: AppConfig) -> None:
        self._store = store
        self._config = config

    async def execute(self, start_token: str, profile: TelegramProfileDto) -> Optional[str]:
        cabinet_url = self._config.web_cabinet_url.strip().rstrip("/")
        if not cabinet_url:
            return None
        ticket = await self._store.take_start(start_token)
        if ticket is None:
            return None
        token = await self._store.issue_signin(
            BotSignInGrantDto(profile=profile, codes=ticket.codes, link_user_id=ticket.link_user_id)
        )
        path = _SIGNIN_PATH if ticket.link_user_id is None else _LINK_PATH
        return f"{cabinet_url}{path}{token}"
