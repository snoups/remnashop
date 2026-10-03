import json

from app.core.bot_signals import RedisBotSignals
from app.core.constants import TRANSLATION_CHANGED_CHANNEL
from app.core.enums import Locale


async def test_translation_changed_publishes_the_new_value(redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(TRANSLATION_CHANGED_CHANNEL)
    await pubsub.get_message(timeout=1)  # discard the subscribe-confirmation message

    await RedisBotSignals(redis).translation_changed(
        Locale.RU, "msg-main-menu", "", "Hello { $name }"
    )

    message = await pubsub.get_message(timeout=1)
    payload = json.loads(message["data"])
    assert payload == {"locale": "ru", "message_id": "msg-main-menu", "value": "Hello { $name }"}

    await pubsub.unsubscribe(TRANSLATION_CHANGED_CHANNEL)
    await pubsub.aclose()


async def test_translation_changed_skips_attribute_keys(redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(TRANSLATION_CHANGED_CHANNEL)
    await pubsub.get_message(timeout=1)  # discard the subscribe-confirmation message

    await RedisBotSignals(redis).translation_changed(Locale.RU, "btn-menu", "subscription", "Sub")

    # fluentogram hot-patches only message-level keys, so nothing is published
    assert await pubsub.get_message(timeout=0.5) is None

    await pubsub.unsubscribe(TRANSLATION_CHANGED_CHANNEL)
    await pubsub.aclose()
