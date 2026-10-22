from typing import Union

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InaccessibleMessage, InputRichMessage, Message, Update
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Keyboard
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from app.core.constants import USER_KEY
from app.core.enums import PurchaseChannel
from app.modules.legal import (
    AcceptLegalDocumentsDto,
    AcceptLegalDocumentsUseCase,
    ListVisibleLegalDocumentsUseCase,
)
from app.modules.settings import GetBotRequirementsUseCase, ReportBotStatusUseCase
from app.modules.users import UserDto
from app.telegram.dialogs.rendering import render_window_text
from app.telegram.i18n import get_translator
from app.telegram.legal_gate import (
    LegalAcceptCallback,
    LegalDocumentCallback,
    gate_message_key,
    legal_gate_keyboard,
)
from app.telegram.middlewares.requirements import ask_requirement
from app.telegram.routers.legal.keyboard import legal_keyboard
from app.telegram.routers.requirements.handlers import continue_requirements

router = Router(name=__name__)


async def send_legal_list(
    message: Union[Message, InaccessibleMessage],
    user: UserDto,
    list_visible_legal_documents: ListVisibleLegalDocumentsUseCase,
    i18n: TranslatorHub,
) -> None:
    runner = get_translator(i18n, user)
    documents = await list_visible_legal_documents.execute(PurchaseChannel.BOT, user.language)
    if not documents:
        await message.answer(
            render_window_text(runner, "msg-legal-empty"), parse_mode=ParseMode.HTML
        )
        return
    await message.answer(
        render_window_text(runner, "msg-legal-list"),
        parse_mode=ParseMode.HTML,
        reply_markup=legal_keyboard(runner, documents),
    )


@router.message(Command("terms"))
async def on_terms_command(
    message: Message,
    user: UserDto,
    list_visible_legal_documents: FromDishka[ListVisibleLegalDocumentsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    logger.info(f"{user.log} Called '/terms' command")
    await send_legal_list(message, user, list_visible_legal_documents, i18n)


@inject
async def on_legal_documents(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    list_visible_legal_documents: FromDishka[ListVisibleLegalDocumentsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    if callback.message is None:
        return
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await send_legal_list(callback.message, user, list_visible_legal_documents, i18n)


@router.callback_query(LegalDocumentCallback.filter())
async def on_legal_document(
    callback: CallbackQuery,
    callback_data: LegalDocumentCallback,
    user: UserDto,
    list_visible_legal_documents: FromDishka[ListVisibleLegalDocumentsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    documents = await list_visible_legal_documents.execute(PurchaseChannel.BOT, user.language)
    document = next((d for d in documents if d.kind == callback_data.kind), None)
    if document is None:
        await callback.answer(get_translator(i18n, user).get("msg-legal-empty"), show_alert=True)
        return
    bot: Bot = callback.bot  # type: ignore[assignment]
    await bot.send_rich_message(
        chat_id=callback.from_user.id,
        rich_message=InputRichMessage(markdown=f"# {document.title}\n\n{document.body}"),
    )
    await callback.answer()


@router.callback_query(LegalAcceptCallback.filter())
async def on_legal_accept(
    callback: CallbackQuery,
    callback_data: LegalAcceptCallback,
    user: UserDto,
    dialog_manager: DialogManager,
    accept_legal_documents: FromDishka[AcceptLegalDocumentsUseCase],
    get_requirements: FromDishka[GetBotRequirementsUseCase],
    redis: FromDishka[Redis],
    i18n: FromDishka[TranslatorHub],
    report: FromDishka[ReportBotStatusUseCase],
    dispatcher: Dispatcher,
) -> None:
    revision_ids = [int(part) for part in callback_data.ids.split(",") if part.isdigit()]
    pending = await accept_legal_documents.execute(
        AcceptLegalDocumentsDto(
            user=user,
            channel=PurchaseChannel.BOT,
            locale=user.language,
            revision_ids=revision_ids,
            client_ip=None,
        )
    )
    if pending.documents:
        runner = get_translator(i18n, user)
        if isinstance(callback.message, Message):
            await callback.message.delete()
        await ask_requirement(
            callback,
            render_window_text(
                runner, "msg-legal-gate-update" if pending.is_update else "msg-legal-gate"
            ),
            legal_gate_keyboard(runner, pending),
            parse_mode=ParseMode.HTML,
        )
        return
    stopped = await redis.getdel(gate_message_key(user.id))
    if stopped is not None and callback.bot is not None:
        if isinstance(callback.message, Message):
            await callback.message.delete()
        await callback.answer()
        # the next requirement, if any, stops it again
        await dispatcher.feed_update(
            callback.bot, Update(update_id=0, message=Message.model_validate_json(stopped))
        )
        return
    requirements = await get_requirements.system()
    await continue_requirements(callback, user, dialog_manager, requirements, redis, i18n, report)
