from typing import Final

import httpx
from loguru import logger
from packaging.version import Version

from src.__version__ import __version__ as local_version
from src.bot.keyboards import get_remnashop_update_keyboard
from src.core.enums import SystemNotificationType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.tasks.notifications import send_system_notification_task

REMOTE_VERSION_URL: Final[str] = (
    "https://raw.githubusercontent.com/snoups/remnashop/main/src/__version__.py"
)


@broker.task(schedule=[{"cron": "*/60 * * * *"}])
async def check_bot_update() -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(REMOTE_VERSION_URL)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch remote version: {resp.text}")
            return

        remote_version = resp.text.strip().split("=")[-1].strip().strip('"').strip("'")

    try:
        lv = Version(local_version)
        rv = Version(remote_version)

        if rv > lv:
            logger.info(f"New version available: {remote_version} (local: {local_version})")
            await send_system_notification_task.kiq(
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
