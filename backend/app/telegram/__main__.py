import asyncio
import sys

import uvicorn
from loguru import logger

from app.core.config import AppConfig
from app.core.constants import TELEGRAM_LOGS_KEY
from app.core.db.crypt_key import assert_crypt_key_matches
from app.core.logger import add_redis_sink, setup_logger
from app.modules.settings import read_bot_settings
from app.telegram.idle_app import get_idle_app

if __name__ == "__main__":
    _config = AppConfig.get()
    setup_logger(_config, "telegram")
    add_redis_sink(_config, TELEGRAM_LOGS_KEY)

    # Startup crashes go through loguru too, so they reach the dashboard log view.
    with logger.catch(onerror=lambda _: sys.exit(1)):
        # before uvicorn's loop: a `factory=True` callable runs inside it, where
        # asyncio.run() fails, so the token is read here and a concrete app built
        asyncio.run(assert_crypt_key_matches(_config))
        _bot_settings = asyncio.run(read_bot_settings(_config))
        if _bot_settings.token is None or _bot_settings.secret_token is None:
            logger.warning(
                "Bot token not set, telegram service is idle. "
                "Set it in Dashboard -> Settings -> Telegram Bot, then press Restart."
            )
            _app = get_idle_app(_config)
        else:
            # aiogram and the bot's graph load only with a token: an idle process
            # stays small, and on a fresh deploy read_translator_hub raises (no
            # active locale yet)
            from app.telegram.i18n import read_translator_hub
            from app.telegram.live_app import build_live_app

            _app = build_live_app(_config, _bot_settings, asyncio.run(read_translator_hub(_config)))

        uvicorn.run(
            app=_app,
            host=_config.bot.host,
            port=_config.bot.port,
            # keep setup_logger's loguru intercept instead of uvicorn's default handlers
            log_config=None,
        )
