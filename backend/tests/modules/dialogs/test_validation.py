from pathlib import Path

import pytest

from app.core.enums import ButtonLinkType, DialogWindowKind, Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogButtonInputDto
from app.modules.dialogs.flows import register_all_flow_metadata
from app.modules.dialogs.validation import (
    MAX_BUTTONS_PER_ROW,
    MAX_TEXT_LENGTH,
    validate_buttons,
    validate_url_value,
    validate_window_text,
    window_text_length,
)
from app.modules.translations.seed import _parse_seed_file


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
        system_conditions={},
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
    validate_window_text("a" * MAX_TEXT_LENGTH, has_banner=False, locale=Locale.EN)
    with pytest.raises(ValidationError):
        validate_window_text("a" * (MAX_TEXT_LENGTH + 1), has_banner=False, locale=Locale.EN)


def test_past_the_caption_limit_a_window_with_a_banner_is_still_valid() -> None:
    # the bot sends it without the banner
    validate_window_text("a" * 2000, has_banner=True, locale=Locale.EN)


def test_premium_emoji_markup_counts_as_its_glyph() -> None:
    # 🙂 is two UTF-16 units
    assert window_text_length("a[🙂](emoji:123)") == 3


def test_window_text_rejects_unclosed_tag() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_window_text("<b>x", has_banner=False, locale=Locale.EN)
    assert exc.value.code == ErrorCode.DIALOG_TEXT_HTML_INVALID


def test_window_text_length_ignores_tags_and_variables() -> None:
    assert window_text_length("<b>ab</b> { $name }c") == 4


def test_window_text_length_takes_the_longest_variant() -> None:
    text = "x { $n ->\n    [one] a\n   *[other] { $k ->\n        [a] bbb\n       *[b] cc\n    }\n}"
    assert window_text_length(text) == len("x bbb")


def test_web_app_button_takes_only_https() -> None:
    (button,) = _url_buttons([0])
    _validate([DialogButtonInputDto(**{**button.__dict__, "link_type": ButtonLinkType.WEB_APP})])
    with pytest.raises(ValidationError):
        _validate(
            [
                DialogButtonInputDto(
                    **{
                        **button.__dict__,
                        "link_type": ButtonLinkType.WEB_APP,
                        "url_value": "http://example.com",
                    }
                )
            ]
        )


def test_a_system_button_keeps_the_catalog_condition() -> None:
    [button] = _url_buttons([0])

    def _check(condition: object) -> None:
        validate_buttons(
            [DialogButtonInputDto(**{**button.__dict__, "visibility_condition": condition})],
            window_key="menu.main",
            window_kind=DialogWindowKind.SEED,
            navigable=set(),
            seed_actions=set(),
            system_conditions={button.text_key: None},
        )

    _check(None)
    with pytest.raises(ValidationError) as error:
        _check("trial_available")
    assert error.value.code is ErrorCode.DIALOG_SYSTEM_BUTTON_CONDITION_LOCKED


@pytest.mark.parametrize("locale", [Locale.EN, Locale.RU])
def test_every_shipped_window_text_is_editable_as_it_ships(locale: Locale) -> None:
    catalog._reset_for_tests()
    register_all_flow_metadata()
    try:
        texts = {
            message_id: value
            for message_id, attribute_id, value in _parse_seed_file(
                Path("assets/translations") / locale.value / "menu.ftl"
            )
            if not attribute_id
        }
        for window in catalog.all_windows():
            for text_key in window.text_keys:
                if text_key in texts:
                    validate_window_text(
                        texts[text_key], has_banner=window.banner_name is not None, locale=locale
                    )
    finally:
        catalog._reset_for_tests()
