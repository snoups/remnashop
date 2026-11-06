import json
from typing import Final, Protocol

from aiogram import Bot
from aiogram.fsm.state import State
from aiogram_dialog import BgManagerFactory, ShowMode, StartMode
from fluentogram import TranslatorHub

from app.core.constants import (
    DIALOG_CONFIG_CHANGED_CHANNEL,
    PAYMENT_OUTCOME_CHANNEL,
    TRANSLATION_CHANGED_CHANNEL,
)
from app.core.enums import PaymentOutcome
from app.modules.translations import fluent_value_source
from app.telegram.signal_listener import SignalHandler, restart_handlers
from app.telegram.states import PaymentResult

_OUTCOME_STATES: Final[dict[PaymentOutcome, State]] = {
    PaymentOutcome.SUCCEEDED: PaymentResult.SUCCESS,
    PaymentOutcome.NOT_FULFILLED: PaymentResult.FAILED,
    PaymentOutcome.CANCELED: PaymentResult.CANCELED,
}


class _Reloadable(Protocol):
    async def reload(self) -> None: ...


def live_update_handlers(cache: _Reloadable, hub: TranslatorHub) -> dict[str, SignalHandler]:
    async def reload_dialogs(_: str) -> None:
        await cache.reload()

    async def patch_translation(data: str) -> None:
        payload = json.loads(data)
        # fluentogram compiles `f"{key} = {value}"`: a raw newline would end the message
        await hub.update_translation(
            payload["locale"], payload["message_id"], fluent_value_source(payload["value"])
        )

    return {
        **restart_handlers(),
        DIALOG_CONFIG_CHANGED_CHANNEL: reload_dialogs,
        TRANSLATION_CHANGED_CHANNEL: patch_translation,
    }


def payment_outcome_handlers(bot: Bot, factory: BgManagerFactory) -> dict[str, SignalHandler]:
    async def show_outcome(data: str) -> None:
        payload = json.loads(data)
        telegram_id = payload["telegram_id"]
        await factory.bg(bot=bot, user_id=telegram_id, chat_id=telegram_id).start(
            _OUTCOME_STATES[PaymentOutcome(payload["outcome"])],
            data={"order_id": payload["order_id"]},
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )

    return {PAYMENT_OUTCOME_CHANNEL: show_outcome}
