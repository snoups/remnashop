from typing import Final

import httpx
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from packaging.version import Version

from src.__version__ import __version__ as local_version
from src.bot.keyboards import get_remnashop_update_keyboard
from src.core.enums import SystemNotificationType
from src.core.storage.keys import LastNotifiedVersionKey
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.redis.repository import RedisRepository
from src.infrastructure.taskiq.broker import broker
from src.services.notification import NotificationService

REMOTE_VERSION_URL: Final[str] = (
    "https://raw.githubusercontent.com/snoups/remnashop/main/src/__version__.py"
)


@broker.task(schedule=[{"cron": "*/60 * * * *"}], retry_on_error=False)
@inject
async def check_bot_update(
    redis_repository: FromDishka[RedisRepository],
    notification_service: FromDishka[NotificationService],
) -> None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(REMOTE_VERSION_URL)
            if resp.status_code != 200:
                logger.error(f"Failed to fetch remote version: {resp.text}")
                return

            remote_version = resp.text.strip().split("=")[-1].strip().strip('"').strip("'")
    except Exception as exception:
        logger.error(f"Failed to get version from github: {exception}")
        return

    try:
        lv = Version(local_version)
        rv = Version(remote_version)

        if rv > lv:
            key = LastNotifiedVersionKey()
            last = await redis_repository.get(key, str)

            if last == remote_version:
                logger.debug(f"Version {remote_version} already notified")
                return

            await redis_repository.set(key, value=remote_version)

            logger.info(f"New version available: {remote_version} (local: {local_version})")
            await notification_service.system_notify(
                ntf_type=SystemNotificationType.BOT_UPDATE,
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-bot-update",
                    i18n_kwargs={
                        "local_version": local_version,
                        "remote_version": remote_version,
                    },
                    reply_markup=get_remnashop_update_keyboard(),
                ),
            )
        elif rv == lv:
            logger.debug(f"Project is up to date ({local_version})")
        else:
            logger.debug(f"Local version is ahead of remote ({local_version} > {remote_version})")
    except Exception as exception:
        logger.error(f"Failed to compare versions: {exception}")
