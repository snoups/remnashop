from typing import Optional
from urllib.parse import quote

from aiogram import Bot

from src.core.config import AppConfig
from src.core.constants import DEEPLINK_PREFIX, PLAN_PREFIX, REFERRAL_PREFIX, T_ME


class BotService:
    def __init__(self, bot: Bot, config: AppConfig):
        self.bot = bot
        self.config = config
        self._bot_username: Optional[str] = None

    async def _get_bot_redirect_url(self) -> str:
        if self._bot_username is None:
            self._bot_username = (await self.bot.get_me()).username
        return f"{T_ME}{self._bot_username}"

    async def get_my_name(self) -> str:
        result = await self.bot.get_my_name()
        return result.name

    async def get_referral_url(self, referral_code: str) -> str:
        base_url = await self._get_bot_redirect_url()
        return f"{base_url}{DEEPLINK_PREFIX}{REFERRAL_PREFIX}{referral_code}"

    async def get_plan_url(self, public_code: str) -> str:
        base_url = await self._get_bot_redirect_url()
        return f"{base_url}{DEEPLINK_PREFIX}{PLAN_PREFIX}{public_code}"

    def get_support_url(self, text: Optional[str]) -> str:
        base_url = f"{T_ME}{self.config.bot.support_username.get_secret_value()}"
        encoded_text = quote(text or "")
        return f"{base_url}?text={encoded_text}"
