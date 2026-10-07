from typing import Any, Final, Optional

import httpx
from loguru import logger

_TELEGRAM_API_URL: Final[str] = "https://api.telegram.org"
_TIMEOUT_SECONDS: Final[float] = 10.0


async def send_telegram_message(token: str, proxy: Optional[str], chat_id: int, text: str) -> bool:
    # plain text: logins and error messages in the payload are user-controlled
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, proxy=proxy) as client:
            response = await client.post(
                f"{_TELEGRAM_API_URL}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
        payload: dict[str, Any] = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning(f"Telegram notification to {chat_id} failed: {type(error).__name__}")
        return False
    if not payload.get("ok"):
        # 403: never pressed /start or blocked the bot
        logger.info(f"Telegram notification to {chat_id} refused: {payload.get('description')}")
        return False
    return True
