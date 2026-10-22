from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from fluentogram import TranslatorRunner

from app.modules.legal import LegalRevisionDto
from app.telegram.legal_gate import LegalDocumentCallback


def legal_keyboard(
    runner: TranslatorRunner, documents: list[LegalRevisionDto]
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=runner.get(f"btn-legal.{document.kind}"),
                    callback_data=LegalDocumentCallback(kind=document.kind).pack(),
                )
            ]
            for document in documents
        ]
    )
