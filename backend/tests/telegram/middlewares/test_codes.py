from aiogram.types import Chat, Message

from app.telegram.middlewares._codes import parse_ad_link_code, parse_referral_code


def _message(text: str) -> Message:
    return Message.model_construct(message_id=1, date=0, chat=Chat(id=1, type="private"), text=text)


def test_parse_ad_link_code_extracts_the_code() -> None:
    assert parse_ad_link_code(_message("/start ad_yt-jan-2026")) == "yt-jan-2026"


def test_parse_ad_link_code_returns_none_for_bare_start() -> None:
    assert parse_ad_link_code(_message("/start")) is None


def test_parse_ad_link_code_returns_none_for_non_ad_prefix() -> None:
    assert parse_ad_link_code(_message("/start ref_someone")) is None


def test_parse_ad_link_code_returns_none_for_empty_code_after_prefix() -> None:
    assert parse_ad_link_code(_message("/start ad_")) is None


def test_parse_ad_link_code_returns_none_when_first_token_is_not_start() -> None:
    assert parse_ad_link_code(_message("hello ad_foo")) is None


def test_parse_ad_link_code_returns_none_for_non_message_event() -> None:
    assert parse_ad_link_code(object()) is None


def test_parse_referral_code_extracts_the_code() -> None:
    assert parse_referral_code(_message("/start ref_AB12CD34")) == "AB12CD34"


def test_parse_referral_code_ignores_an_ad_link() -> None:
    assert parse_referral_code(_message("/start ad_yt-jan")) is None
