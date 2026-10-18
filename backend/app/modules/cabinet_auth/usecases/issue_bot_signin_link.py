from typing import Final, Optional

from app.core.config import AppConfig
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import BotSignInGrantDto, BotSignInLinkDto, TelegramProfileDto

# a fragment, not a query: it never reaches a proxy log or a Referer
_SIGNIN_PATH: Final[str] = "/login/bot#token="
_LINK_PATH: Final[str] = "/link/bot#token="


class IssueBotSignInLinkUseCase:
    """The bot's side: spends the cabinet's start link, hands back a one-time sign-in URL."""

    def __init__(self, store: DeeplinkStore, config: AppConfig) -> None:
        self._store = store
        self._config = config

    async def execute(
        self, start_token: str, profile: TelegramProfileDto
    ) -> Optional[BotSignInLinkDto]:
        cabinet_url = self._config.cabinet.url
        if not cabinet_url:
            return None
        ticket = await self._store.take_start(start_token)
        if ticket is None:
            return None
        token = await self._store.issue_signin(
            BotSignInGrantDto(profile=profile, codes=ticket.codes, link_user_id=ticket.link_user_id)
        )
        is_link = ticket.link_user_id is not None
        path = _LINK_PATH if is_link else _SIGNIN_PATH
        return BotSignInLinkDto(url=f"{cabinet_url}{path}{token}", is_link=is_link)
