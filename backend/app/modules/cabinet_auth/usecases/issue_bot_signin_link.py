from typing import Final, Optional

from app.core.config import AppConfig
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.dto import BotSignInGrantDto, TelegramProfileDto

_SIGNIN_PATH: Final[str] = "/login/bot?token="


class IssueBotSignInLinkUseCase:
    """The bot's side: spends the cabinet's start link, hands back a one-time sign-in URL."""

    def __init__(self, store: DeeplinkStore, config: AppConfig) -> None:
        self._store = store
        self._config = config

    async def execute(self, start_token: str, profile: TelegramProfileDto) -> Optional[str]:
        cabinet_url = self._config.web_cabinet_url.strip().rstrip("/")
        if not cabinet_url:
            return None
        pending = await self._store.take_start(start_token)
        if pending is None:
            return None
        token = await self._store.issue_signin(
            BotSignInGrantDto(profile=profile, codes=pending.codes)
        )
        return f"{cabinet_url}{_SIGNIN_PATH}{token}"
