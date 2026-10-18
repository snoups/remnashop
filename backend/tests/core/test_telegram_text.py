import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.telegram_text import (
    PREMIUM_EMOJI_RE,
    html_text_length,
    telegram_length,
    validate_telegram_html,
)


def test_premium_emoji_markup_counts_as_its_glyph() -> None:
    markup = "[😀](emoji:5368324170671202286) hi"
    expected_length = len("😀 hi".encode("utf-16-le")) // 2
    assert telegram_length(markup) == expected_length


def test_astral_emoji_counts_two_units() -> None:
    assert telegram_length("😀") == 2


def test_regex_captures_glyph_and_id() -> None:
    match = PREMIUM_EMOJI_RE.search("[🔥](emoji:42)")
    assert match is not None and match.groups() == ("🔥", "42")


@pytest.mark.parametrize(
    "text",
    [
        '<b>ok</b> <i>x</i> <a href="https://a.b">l</a> <tg-spoiler>s</tg-spoiler>',
        "<blockquote>q</blockquote><pre>code</pre> a &amp; b",
        "5 &lt; 6",
        "<b>{ $user_name }</b> [⭐](emoji:123)",
    ],
)
def test_valid_html(text: str) -> None:
    validate_telegram_html(text, code=ErrorCode.DIALOG_TEXT_HTML_INVALID)


@pytest.mark.parametrize(
    "text",
    [
        "<div>x</div>",
        "<b>unclosed",
        "<b><i>x</b></i>",
        '<a href="javascript:alert(1)">x</a>',
        "<a>no href</a>",
        "</b>",
        "plain text with 5 < 6",
        "<{ $name }>",
        "a<!-- c -->b",
        "<!DOCTYPE html>",
        "<?php x ?>",
        "<![CDATA[x]]>",
    ],
)
def test_invalid_html(text: str) -> None:
    with pytest.raises(ValidationError) as error:
        validate_telegram_html(text, code=ErrorCode.DIALOG_TEXT_HTML_INVALID)
    assert error.value.code is ErrorCode.DIALOG_TEXT_HTML_INVALID


def test_validate_raises_with_given_code() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_telegram_html("<b>x", code=ErrorCode.DIALOG_TEXT_HTML_INVALID)
    assert exc.value.code == ErrorCode.DIALOG_TEXT_HTML_INVALID


def test_html_text_length_ignores_tags_and_entities() -> None:
    assert html_text_length("<b>ab</b>&lt;[⭐](emoji:1)") == 4
