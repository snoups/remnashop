import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.broadcasts.content import render_text
from app.modules.broadcasts.email_html import (
    email_image_ids,
    email_text,
    style_email_html,
    validate_email_html,
)

TIPTAP = (
    "<h1>Sale</h1><p>Hi <strong>{ $name }</strong>, <em>new</em> <u>plans</u> <s>old</s></p>"
    "<ul><li><p>one</p></li></ul><ol><li><p>two</p></li></ol><blockquote><p>q</p></blockquote>"
    '<hr><p><a href="https://shop.example/x">link</a><br>line</p>'
    '<p><a data-button="" href="https://shop.example/buy">Buy</a></p>'
    '<img src="bc-image:7" alt="banner">'
)


def test_accepts_tiptap_output() -> None:
    validate_email_html(TIPTAP)


@pytest.mark.parametrize(
    "html",
    [
        '<img src="https://evil.example/x.png">',
        '<img src="bc-image:7" onerror="alert(1)">',
        '<p style="color:red">x</p>',
        '<p class="x">x</p>',
        '<a href="javascript:alert(1)">x</a>',
        '<a href="data:text/html,x">x</a>',
        '<a href="https://a.example/ x">x</a>',
        '<a href="https://a.example/\tx">x</a>',
        '<a href="https://a.example/\x00x">x</a>',
        '<img src="mailto:a@b.example">',
        "<script>alert(1)</script>",
        "<iframe></iframe>",
        "<!-- c -->",
        "<p>unclosed",
    ],
)
def test_rejects_foreign_and_scripted_markup(html: str) -> None:
    with pytest.raises(ValidationError) as caught:
        validate_email_html(html)
    assert caught.value.code is ErrorCode.BROADCAST_EMAIL_HTML_INVALID


def test_mailto_link_allowed() -> None:
    validate_email_html('<p><a href="mailto:help@shop.example">help</a></p>')


def test_image_ids() -> None:
    assert email_image_ids(TIPTAP + '<img src="bc-image:9">') == {7, 9}


def test_style_inlines_and_maps_images() -> None:
    styled = style_email_html(TIPTAP, accent="#ff0000", image_src=lambda i: f"cid:img-{i}")
    assert 'src="cid:img-7"' in styled
    assert "style=" in styled
    assert "background:#ff0000" in styled  # the button
    assert "bc-image" not in styled
    assert "data-button" not in styled


def test_style_escapes_image_src() -> None:
    styled = style_email_html('<img src="bc-image:1">', accent="#f00", image_src=lambda i: 'x"y')
    assert 'src="x&quot;y"' in styled


def test_text_version() -> None:
    text = email_text(TIPTAP)
    assert "Sale" in text
    assert "link (https://shop.example/x)" in text
    assert "Buy: https://shop.example/buy" in text
    assert "<" not in text


def test_variables_escaped_in_subject_and_body() -> None:
    body = render_text("<p>{ $name }</p>", {"name": "<b>x</b>"})
    validate_email_html(body)  # escaped value is plain text
    assert "&lt;b&gt;" in body


@pytest.mark.parametrize(
    "src",
    [
        'src="bc-image:7"',
        "src='bc-image:7'",
        "src=bc-image:7",
        'SRC="bc-image:7"',
        'src = "bc-image:7"',
        'src="bc-image:&#55;"',
        'src="bc-image:7\n"',
    ],
)
def test_image_ids_match_what_the_styler_rewrites(src: str) -> None:
    html = f"<img {src}>"
    styled = style_email_html(html, accent="#f00", image_src=lambda i: f"cid:img-{i}")
    ids = email_image_ids(html)
    assert ("cid:img-7" in styled) == (ids == {7})


@pytest.mark.parametrize("src", ['src="bc-image:7"', 'src="bc-image:٧"', 'src="bc-image:7\n"'])
def test_image_src_is_strict(src: str) -> None:
    if src == 'src="bc-image:7"':
        assert email_image_ids(f"<img {src}>") == {7}
        return
    assert email_image_ids(f"<img {src}>") == set()
    with pytest.raises(ValidationError):
        validate_email_html(f"<img {src}>")


@pytest.mark.parametrize(
    "html",
    ['<p>x</p><a href="javascript:1"', '<p>x</p><img src="bc-image:1" onerror="x"', "<p>x</p><a"],
)
def test_rejects_truncated_tag(html: str) -> None:
    with pytest.raises(ValidationError):
        validate_email_html(html)


def test_styler_drops_foreign_tags() -> None:
    styled = style_email_html(
        '<p>a <tg-emoji emoji-id="123">x</tg-emoji></p>', accent="#f00", image_src=str
    )
    assert "tg-emoji" not in styled
    assert ">a x<" in styled
