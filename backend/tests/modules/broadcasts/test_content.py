import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.broadcasts.content import render_text, used_variables, validate_html


def test_used_variables_accepts_spacing_variants() -> None:
    text = "Hi { $name }, {$plan} and {  $days_left  }"
    assert used_variables(text) == {"name", "plan", "days_left"}


def test_render_escapes_values_and_keeps_markup() -> None:
    result = render_text("<b>Hi { $name }</b>", {"name": "<b>Bob & Co"})
    assert result == "<b>Hi &lt;b&gt;Bob &amp; Co</b>"


def test_render_unknown_value_becomes_dash() -> None:
    assert render_text("{ $plan }", {}) == "—"


def test_render_converts_premium_emoji() -> None:
    assert render_text("[🔥](emoji:42) go", {}) == '<tg-emoji emoji-id="42">🔥</tg-emoji> go'


def test_render_escapes_emoji_like_names() -> None:
    result = render_text("{ $name }", {"name": "[🔥](emoji:1)"})
    assert result == "[🔥](emoji:1)"


@pytest.mark.parametrize(
    "text",
    [
        '<b>ok</b> <i>x</i> <a href="https://a.b">l</a> <tg-spoiler>s</tg-spoiler>',
        "<blockquote>q</blockquote><pre>code</pre> a &amp; b",
        "5 &lt; 6",
    ],
)
def test_valid_html(text: str) -> None:
    validate_html(text)


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
    ],
)
def test_invalid_html(text: str) -> None:
    with pytest.raises(ValidationError) as error:
        validate_html(text)
    assert error.value.code is ErrorCode.BROADCAST_HTML_INVALID


@pytest.mark.parametrize(
    "text",
    ["a<!-- c -->b", "<!DOCTYPE html>", "<?php x ?>", "<![CDATA[x]]>"],
)
def test_comments_and_declarations_are_rejected(text: str) -> None:
    with pytest.raises(ValidationError) as error:
        validate_html(text)
    assert error.value.code is ErrorCode.BROADCAST_HTML_INVALID
