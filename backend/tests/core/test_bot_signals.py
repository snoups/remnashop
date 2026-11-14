import json

from app.core.bot_signals import RedisBotSignals
from app.core.constants import (
    DIALOG_CONFIG_CHANGED_CHANNEL,
    PAYMENT_OUTCOME_CHANNEL,
    TRANSLATION_CHANGED_CHANNEL,
)
from app.core.enums import Locale, PaymentOutcome


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


async def test_translation_changed_reloads_everything_for_an_attribute_key(redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(TRANSLATION_CHANGED_CHANNEL, DIALOG_CONFIG_CHANGED_CHANNEL)
    for _ in range(2):
        await pubsub.get_message(timeout=1)  # discard the subscribe confirmations

    await RedisBotSignals(redis).translation_changed(Locale.RU, "btn-menu", "subscription", "Sub")

    # fluentogram can't hot-patch an attribute, so the bot reloads in full
    message = await pubsub.get_message(timeout=1)
    assert message is not None and message["channel"] == DIALOG_CONFIG_CHANGED_CHANNEL
    assert await pubsub.get_message(timeout=0.5) is None

    await pubsub.unsubscribe(TRANSLATION_CHANGED_CHANNEL, DIALOG_CONFIG_CHANGED_CHANNEL)
    await pubsub.aclose()


async def test_payment_outcome_reports_receivers(redis) -> None:
    signals = RedisBotSignals(redis)
    assert await signals.payment_outcome(5, 7, PaymentOutcome.CANCELED) == 0

    pubsub = redis.pubsub()
    await pubsub.subscribe(PAYMENT_OUTCOME_CHANNEL)
    await pubsub.get_message(timeout=1)  # discard the subscribe-confirmation message

    assert await signals.payment_outcome(5, 7, PaymentOutcome.CANCELED) == 1

    message = await pubsub.get_message(timeout=1)
    assert json.loads(message["data"]) == {"telegram_id": 5, "order_id": 7, "outcome": "CANCELED"}

    await pubsub.unsubscribe(PAYMENT_OUTCOME_CHANNEL)
    await pubsub.aclose()
