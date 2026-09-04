from redis.asyncio import Redis

from app.core.constants import DIALOG_CONFIG_CHANGED_CHANNEL


async def publish_dialog_change(redis: Redis) -> None:
    # fire-and-forget: no telegram subscriber -> dropped; its next reload reads fresh
    await redis.publish(DIALOG_CONFIG_CHANGED_CHANNEL, "changed")
