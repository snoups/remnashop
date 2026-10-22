from typing import Final

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from fluentogram import TranslatorRunner

from app.core.constants import REDIS_KEY_PREFIX, TIME_1M
from app.core.enums import LegalDocumentKind
from app.modules.legal import PendingLegalDocumentsDto


class LegalDocumentCallback(CallbackData, prefix="legal"):
    kind: LegalDocumentKind


class LegalAcceptCallback(CallbackData, prefix="legal_accept"):
    # the shown revision ids, comma-joined
    ids: str


# opening a document and accepting it must work while the gate is up
LEGAL_GATE_CALLBACK_PREFIXES: Final[tuple[str, ...]] = (
    f"{LegalDocumentCallback.__prefix__}:",
    f"{LegalAcceptCallback.__prefix__}:",
)


# the message the gate stopped, replayed once the documents are accepted (a /start deep link)
GATE_MESSAGE_TTL_S: Final[int] = 10 * TIME_1M


def gate_message_key(user_id: int) -> str:
    return f"{REDIS_KEY_PREFIX}legal_gate_message:{user_id}"


def legal_gate_keyboard(
    runner: TranslatorRunner, pending: PendingLegalDocumentsDto
) -> InlineKeyboardMarkup:
    ids = ",".join(str(document.id) for document in pending.documents)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *(
                [
                    InlineKeyboardButton(
                        text=runner.get(f"btn-legal.{document.kind}"),
                        callback_data=LegalDocumentCallback(kind=document.kind).pack(),
                    )
                ]
                for document in pending.documents
            ),
            [
                InlineKeyboardButton(
                    text=runner.get("btn-legal-gate.accept"),
                    callback_data=LegalAcceptCallback(ids=ids).pack(),
                )
            ],
        ]
    )
