import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, User
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.core.enums import Currency, LegalDocumentKind, Locale, PurchaseChannel
from app.modules.legal import LegalRevisionDto, PendingLegalDocumentsDto
from app.modules.settings import BotRequirementsDto
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.subscriptions import PlanCatalogDto
from app.modules.users import UserDto
from app.telegram.i18n import build_translator_hub
from app.telegram.legal_gate import LegalAcceptCallback, LegalDocumentCallback, gate_message_key
from app.telegram.middlewares.requirements import CHANNEL_CHECK_CALLBACK
from app.telegram.routers.legal.handlers import (
    on_legal_accept,
    on_legal_document,
    on_terms_command,
)
from app.telegram.routers.legal.keyboard import legal_keyboard
from app.telegram.routers.purchase.getters import confirm_getter
from tests.fakes.aiogram_bot import FakeAiogramSession
from tests.seeded_translations import seeded_fluent_source

_USER: Any = SimpleNamespace(id=1, telegram_id=9, language=Locale.EN, log="[user 1]")


def _hub(locale: Locale = Locale.EN) -> Any:
    return build_translator_hub([locale], {locale: seeded_fluent_source(locale)}, locale)


def _revision(
    kind: LegalDocumentKind, title: str = "Offer", body: str = "Text"
) -> LegalRevisionDto:
    return LegalRevisionDto(
        id=1,
        kind=kind,
        locale=Locale.EN,
        channel=None,
        title=title,
        body=body,
        created_at=datetime(2026, 10, 21, tzinfo=timezone.utc),
    )


def _visible(documents: list[LegalRevisionDto]) -> Any:
    return MagicMock(execute=AsyncMock(return_value=documents))


def _bot(session: FakeAiogramSession) -> Bot:
    return Bot("42:TEST", session=session)


def _message(bot: Bot) -> Message:
    return Message(
        message_id=1,
        date=datetime(2026, 10, 21, tzinfo=timezone.utc),
        chat=Chat(id=9, type="private"),
        from_user=User(id=9, is_bot=False, first_name="Ann"),
        text="/terms",
    ).as_(bot)


def _callback(bot: Bot, kind: LegalDocumentKind) -> CallbackQuery:
    return CallbackQuery(
        id="c1",
        from_user=User(id=9, is_bot=False, first_name="Ann"),
        chat_instance="i",
        data=LegalDocumentCallback(kind=kind).pack(),
    ).as_(bot)


def test_terms_is_a_bot_command() -> None:
    assert "terms" in {command.command for command in BOT_COMMANDS}


async def test_terms_lists_visible_documents() -> None:
    session = FakeAiogramSession({"SendMessage": True})
    visible = _visible(
        [_revision(LegalDocumentKind.OFFER), _revision(LegalDocumentKind.PRIVACY_POLICY)]
    )
    hub = _hub()
    runner = hub.get_translator_by_locale("en")

    await on_terms_command(_message(_bot(session)), _USER, visible, hub)

    visible.execute.assert_awaited_once_with(PurchaseChannel.BOT, Locale.EN)
    [sent] = session.called("SendMessage")
    assert sent.text == runner.get("msg-legal-list")
    buttons = [row[0] for row in sent.reply_markup.inline_keyboard]
    assert [b.text for b in buttons] == [
        runner.get("btn-legal.OFFER"),
        runner.get("btn-legal.PRIVACY_POLICY"),
    ]
    assert buttons[0].callback_data == LegalDocumentCallback(kind=LegalDocumentKind.OFFER).pack()


async def test_terms_without_documents_sends_nothing() -> None:
    session = FakeAiogramSession({"SendMessage": True})

    await on_terms_command(_message(_bot(session)), _USER, _visible([]), _hub())

    assert session.called("SendMessage") == []


async def test_document_callback_sends_rich_message() -> None:
    session = FakeAiogramSession({"SendRichMessage": True, "AnswerCallbackQuery": True})
    visible = _visible(
        [_revision(LegalDocumentKind.OFFER, title="Public offer", body="**1.** Terms")]
    )

    await on_legal_document(
        _callback(_bot(session), LegalDocumentKind.OFFER),
        LegalDocumentCallback(kind=LegalDocumentKind.OFFER),
        _USER,
        visible,
        _hub(),
    )

    [sent] = session.called("SendRichMessage")
    assert sent.chat_id == 9
    assert sent.rich_message.markdown == "# Public offer\n\n**1.** Terms"


def _list_callback(bot: Bot, kind: LegalDocumentKind) -> CallbackQuery:
    keyboard = legal_keyboard(_hub().get_translator_by_locale("en"), [_revision(kind)])
    message = Message(
        message_id=5,
        date=datetime.now(timezone.utc),
        chat=Chat(id=9, type="private"),
        reply_markup=keyboard,
    ).as_(bot)
    return CallbackQuery(
        id="c1",
        from_user=User(id=9, is_bot=False, first_name="Ann"),
        chat_instance="i",
        data=LegalDocumentCallback(kind=kind).pack(),
        message=message,
    ).as_(bot)


async def test_document_gone_by_the_tap_redraws_the_list_silently() -> None:
    session = FakeAiogramSession({"AnswerCallbackQuery": True, "EditMessageReplyMarkup": True})

    await on_legal_document(
        _list_callback(_bot(session), LegalDocumentKind.OFFER),
        LegalDocumentCallback(kind=LegalDocumentKind.OFFER),
        _USER,
        _visible([_revision(LegalDocumentKind.PRIVACY_POLICY)]),
        _hub(),
    )

    assert session.called("SendRichMessage") == []
    [answer] = session.called("AnswerCallbackQuery")
    assert answer.text is None
    [edit] = session.called("EditMessageReplyMarkup")
    assert [row[0].callback_data for row in edit.reply_markup.inline_keyboard] == [
        LegalDocumentCallback(kind=LegalDocumentKind.PRIVACY_POLICY).pack()
    ]


async def test_last_document_gone_by_the_tap_removes_the_list() -> None:
    session = FakeAiogramSession({"AnswerCallbackQuery": True, "DeleteMessage": True})

    await on_legal_document(
        _list_callback(_bot(session), LegalDocumentKind.OFFER),
        LegalDocumentCallback(kind=LegalDocumentKind.OFFER),
        _USER,
        _visible([]),
        _hub(),
    )

    assert len(session.called("DeleteMessage")) == 1


@pytest.mark.parametrize("locale", [Locale.EN, Locale.RU])
async def test_confirm_window_shows_terms_notice_only_with_documents(locale: Locale) -> None:
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: SimpleNamespace(id=1, language=locale)}
    manager.dialog_data = {
        "plan_id": 10,
        "purchase_type": "NEW",
        "prices": {"USD": "2.5"},
        "plan_name": "Plan",
        "duration_days": 30,
        "currency": "USD",
        "gateway_type": "CRYPTOMUS",
    }
    hub = _hub(locale)

    async def _text(documents: list[LegalRevisionDto]) -> str:
        data = await confirm_getter.__dishka_orig_func__(
            manager,
            list_active_plans=AsyncMock(
                return_value=PlanCatalogDto(plans=[], anchor_currency=Currency.USD)
            ),
            list_own_subscriptions=AsyncMock(return_value=[]),
            list_visible_legal_documents=_visible(documents),
            i18n=hub,
        )
        return str(data["window_text"])

    with_documents = await _text([_revision(LegalDocumentKind.OFFER)])
    without = await _text([])

    assert "/terms" in with_documents.splitlines()[-1]
    assert "/terms" not in without
    assert without.endswith("</blockquote>")


@pytest.mark.parametrize("locale", [Locale.EN, Locale.RU])
def test_legal_texts_exist_in_each_locale(locale: Locale) -> None:
    runner = _hub(locale).get_translator_by_locale(locale.value)
    for key in (
        "msg-legal-list",
        "frg-purchase-terms-notice",
        "btn-menu.legal",
        "command.terms",
        *(f"btn-legal.{kind}" for kind in LegalDocumentKind),
    ):
        assert runner.get(key) != key, key


class _GetRequirements:
    def __init__(self, requirements: BotRequirementsDto) -> None:
        self._requirements = requirements

    @property
    def system(self) -> "_GetRequirements":
        return self

    async def __call__(self) -> BotRequirementsDto:
        return self._requirements


class _MemberBot:
    def __init__(self, status: str) -> None:
        self.status = status

    async def get_chat_member(self, chat_id: int, user_id: int) -> Any:
        return SimpleNamespace(status=self.status)


_GATE_USER = UserDto(id=1, name="c", telegram_id=46, language=Locale.EN)
_CHANNEL = BotRequirementsDto(channel_required=True, channel_id=-100, channel_url="https://t.me/x")


async def _press_accept(
    pending_after: PendingLegalDocumentsDto,
    requirements: BotRequirementsDto,
    status: str,
    redis: Redis,
    dispatcher: Any = None,
) -> tuple[MagicMock, AsyncMock, AsyncMock]:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    message.delete = AsyncMock()
    callback = MagicMock(spec=CallbackQuery)
    callback.bot = _MemberBot(status)
    callback.message = message
    callback.answer = AsyncMock()
    dialog_manager = MagicMock(start=AsyncMock())
    accept = MagicMock(execute=AsyncMock(return_value=pending_after))
    await on_legal_accept(
        callback,
        LegalAcceptCallback(ids="1,2"),
        _GATE_USER,
        dialog_manager,
        accept,
        _GetRequirements(requirements),  # type: ignore[arg-type]
        redis,
        _hub(),
        AsyncMock(),
        dispatcher or MagicMock(feed_update=AsyncMock()),
    )
    (call,) = accept.execute.await_args_list
    assert call.args[0].revision_ids == [1, 2]
    assert call.args[0].channel == PurchaseChannel.BOT
    return message, dialog_manager.start, callback.answer


@pytest.fixture
async def redis(config: AppConfig) -> Any:
    client = Redis.from_url(config.redis.dsn, decode_responses=True)
    yield client
    await client.aclose()


_ACCEPTED = PendingLegalDocumentsDto(documents=[], is_update=False)


async def test_accept_opens_main_menu(redis: Redis) -> None:
    message, start, _ = await _press_accept(_ACCEPTED, BotRequirementsDto(), "member", redis)

    start.assert_awaited_once()
    message.answer.assert_not_awaited()


async def test_accept_then_channel_requirement_is_shown(redis: Redis) -> None:
    message, start, _ = await _press_accept(_ACCEPTED, _CHANNEL, "left", redis)

    start.assert_not_awaited()
    assert "reply_markup" in message.answer.await_args.kwargs
    keyboard = message.answer.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[1][0].callback_data == CHANNEL_CHECK_CALLBACK


async def test_accept_with_stale_revision_resends_screen(redis: Redis) -> None:
    fresh = PendingLegalDocumentsDto(
        documents=[_revision(LegalDocumentKind.USER_AGREEMENT).model_copy(update={"id": 7})],
        is_update=False,
    )

    message, start, _ = await _press_accept(fresh, BotRequirementsDto(), "member", redis)

    start.assert_not_awaited()
    keyboard = message.answer.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[-1][0].callback_data == LegalAcceptCallback(ids="7").pack()


async def test_accept_replays_the_stopped_message(redis: Redis) -> None:
    stored = Message(
        message_id=5,
        date=datetime(2026, 10, 21, tzinfo=timezone.utc),
        chat=Chat(id=46, type="private"),
        from_user=User(id=46, is_bot=False, first_name="Ann"),
        text="/start webauth_abc",
    )
    await redis.set(gate_message_key(_GATE_USER.id), stored.model_dump_json(), ex=60)
    dispatcher = MagicMock(feed_update=AsyncMock())

    message, start, _ = await _press_accept(
        _ACCEPTED, BotRequirementsDto(), "member", redis, dispatcher
    )
    await asyncio.sleep(0)

    start.assert_not_awaited()
    message.delete.assert_awaited_once()
    update = dispatcher.feed_update.await_args.args[1]
    assert update.message.text == "/start webauth_abc"
    assert await redis.get(gate_message_key(_GATE_USER.id)) is None
