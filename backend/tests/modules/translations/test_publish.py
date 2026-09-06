import json

from app.core.constants import TRANSLATION_CHANGED_CHANNEL
from app.core.enums import Locale
from app.modules.translations import publish_translation_change


async def test_publish_translation_change(redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(TRANSLATION_CHANGED_CHANNEL)
    await pubsub.get_message(timeout=1)  # discard the subscribe-confirmation message

    await publish_translation_change(
        redis, Locale.RU, "msg-main-menu", "Hello { $name }", attribute_id=""
    )

    message = await pubsub.get_message(timeout=1)
    payload = json.loads(message["data"])
    assert payload == {"locale": "ru", "message_id": "msg-main-menu", "value": "Hello { $name }"}

    await pubsub.unsubscribe(TRANSLATION_CHANGED_CHANNEL)
    await pubsub.aclose()


async def test_publish_translation_change_skips_attribute_keyed(redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(TRANSLATION_CHANGED_CHANNEL)
    await pubsub.get_message(timeout=1)  # discard the subscribe-confirmation message

    await publish_translation_change(
        redis, Locale.RU, "btn-menu", "Sub", attribute_id="subscription"
    )

    # fluentogram can only hot-patch message-level keys -- nothing is published.
    assert await pubsub.get_message(timeout=0.5) is None

    await pubsub.unsubscribe(TRANSLATION_CHANGED_CHANNEL)
    await pubsub.aclose()
