import pytest

from app.core.enums import ButtonLinkType, DialogWindowKind, Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogButtonInputDto
from app.modules.dialogs.validation import (
    MAX_BUTTONS_PER_ROW,
    MAX_CAPTION_LENGTH,
    validate_buttons,
    validate_url_value,
    validate_window_text,
)


def _url_buttons(rows: list[int], *, hidden: bool = False) -> list[DialogButtonInputDto]:
    return [
        DialogButtonInputDto(
            row=row,
            column=column,
            text_key=f"{catalog.CUSTOM_TEXT_KEY_PREFIX}{row}-{column}",
            link_type=ButtonLinkType.URL,
            url_value="https://example.com",
            is_hidden=hidden,
        )
        for column, row in enumerate(rows)
    ]


def _validate(buttons: list[DialogButtonInputDto]) -> None:
    validate_buttons(
        buttons,
        window_key="custom-x",
        window_kind=DialogWindowKind.CUSTOM,
        navigable=set(),
        seed_actions=set(),
        system_text_keys=set(),
    )


def test_row_limit() -> None:
    _validate(_url_buttons([0] * MAX_BUTTONS_PER_ROW))
    with pytest.raises(ValidationError):
        _validate(_url_buttons([0] * (MAX_BUTTONS_PER_ROW + 1)))


def test_hidden_buttons_do_not_count_toward_the_row_limit() -> None:
    buttons = _url_buttons([0] * MAX_BUTTONS_PER_ROW)
    extra = _url_buttons([0], hidden=True)[0]
    _validate([*buttons, DialogButtonInputDto(**{**extra.__dict__, "column": 99})])


@pytest.mark.parametrize("url", ["https://", "tg://", "https://exa mple.com", " https://a.b"])
def test_rejects_unusable_url(url: str) -> None:
    with pytest.raises(ValidationError):
        validate_url_value(url)


def test_window_text_limits() -> None:
    validate_window_text("", has_banner=True, locale=Locale.EN)
    with pytest.raises(ValidationError):
        validate_window_text("  ", has_banner=False, locale=Locale.EN)
    validate_window_text("a" * MAX_CAPTION_LENGTH, has_banner=True, locale=Locale.EN)
    with pytest.raises(ValidationError):
        validate_window_text("a" * (MAX_CAPTION_LENGTH + 1), has_banner=True, locale=Locale.EN)
    validate_window_text("a" * (MAX_CAPTION_LENGTH + 1), has_banner=False, locale=Locale.EN)


def test_premium_emoji_markup_counts_as_its_glyph() -> None:
    text = "a" * (MAX_CAPTION_LENGTH - 1) + "[🙂](emoji:123)"
    with pytest.raises(ValidationError):
        # 🙂 is two UTF-16 units
        validate_window_text(text, has_banner=True, locale=Locale.EN)
    validate_window_text(
        "a" * (MAX_CAPTION_LENGTH - 2) + "[🙂](emoji:123)", has_banner=True, locale=Locale.EN
    )


def test_window_text_rejects_unclosed_tag() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_window_text("<b>x", has_banner=False, locale=Locale.EN)
    assert exc.value.code == ErrorCode.DIALOG_TEXT_HTML_INVALID


def test_window_text_length_ignores_tags() -> None:
    validate_window_text(
        "<b>" + "a" * MAX_CAPTION_LENGTH + "</b>", has_banner=True, locale=Locale.EN
    )
