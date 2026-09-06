import json

from redis.asyncio import Redis

from app.core.constants import TRANSLATION_CHANGED_CHANNEL
from app.core.enums import Locale


async def publish_translation_change(
    redis: Redis, locale: Locale, message_id: str, value: str, *, attribute_id: str
) -> None:
    # fire-and-forget: no telegram subscriber -> dropped; the DB write already
    # landed, so the live hub just serves stale text until the next actual
    # change (or a restart) -- same tolerance as dialogs' publish_dialog_change.
    if attribute_id != "":
        # fluentogram's TranslatorHub.update_translation() can only hot-patch a
        # message-level key in place -- a dotted/attribute key raises KeyError
        # inside it. Attribute-keyed edits still land in the DB and apply on the
        # next bot restart; we just don't try to relay them to the live hub.
        return
    payload = json.dumps({"locale": locale.value, "message_id": message_id, "value": value})
    await redis.publish(TRANSLATION_CHANGED_CHANNEL, payload)
