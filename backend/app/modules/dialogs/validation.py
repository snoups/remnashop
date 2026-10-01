from collections import Counter
from typing import Final

from app.core.enums import ButtonLinkType, DialogWindowKind, Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogButtonInputDto

# Telegram's own limits; going over any of them fails the whole message.
MAX_BUTTONS_PER_ROW: Final[int] = 8
MAX_BUTTONS: Final[int] = 100
MAX_TEXT_LENGTH: Final[int] = 4096
# A window with a banner goes out as a photo, and this is the caption limit.
MAX_CAPTION_LENGTH: Final[int] = 1024


def validate_window_text(value: str, *, has_banner: bool, locale: Locale) -> None:
    if not has_banner and not value.strip():
        raise ValidationError(
            f"Window text ({locale}) cannot be empty without a banner",
            code=ErrorCode.DIALOG_TEXT_EMPTY,
        )
    # Telegram counts UTF-16 code units of the text as sent, where premium
    # emoji markup is just its glyph. Fluent placeables count as written --
    # what a variable expands to is only known at render time.
    sent = catalog.PREMIUM_EMOJI_RE.sub(r"\1", value)
    length = len(sent.encode("utf-16-le")) // 2
    limit = MAX_CAPTION_LENGTH if has_banner else MAX_TEXT_LENGTH
    if length > limit:
        raise ValidationError(
            f"Window text ({locale}) is {length} characters long, the limit is {limit}"
            + (" with a banner" if has_banner else ""),
            code=ErrorCode.DIALOG_TEXT_TOO_LONG,
        )


def validate_url_value(url_value: str) -> None:
    if any(char.isspace() for char in url_value):
        raise ValidationError("URL cannot contain spaces", code=ErrorCode.DIALOG_URL_HAS_SPACES)
    for name in catalog.URL_VARIABLE_RE.findall(url_value):
        if name not in catalog.variable_keys():
            raise ValidationError(
                f"Unknown URL variable: {name}", code=ErrorCode.DIALOG_URL_VARIABLE_UNKNOWN
            )
    literal = catalog.URL_VARIABLE_RE.sub("", url_value)
    if literal and not literal.startswith(catalog.URL_SCHEMES):
        raise ValidationError(
            f"URL must start with one of: {', '.join(catalog.URL_SCHEMES)}",
            code=ErrorCode.DIALOG_URL_SCHEME_INVALID,
        )
    if url_value in catalog.URL_SCHEMES:
        raise ValidationError("URL has nothing after the scheme", code=ErrorCode.DIALOG_URL_EMPTY)


def validate_buttons(
    buttons: list[DialogButtonInputDto],
    *,
    window_key: str,
    window_kind: DialogWindowKind,
    navigable: set[str],
    seed_actions: set[str],
    system_text_keys: set[str],
) -> None:
    shown = [button for button in buttons if not button.is_hidden]
    if len(shown) > MAX_BUTTONS:
        raise ValidationError(
            f"'{window_key}' has {len(shown)} buttons, the limit is {MAX_BUTTONS}",
            code=ErrorCode.DIALOG_BUTTON_LIMIT_REACHED,
        )
    per_row = Counter(button.row for button in shown)
    for row, count in per_row.items():
        if count > MAX_BUTTONS_PER_ROW:
            raise ValidationError(
                f"Row {row} in '{window_key}' has {count} buttons, "
                f"the limit is {MAX_BUTTONS_PER_ROW}",
                code=ErrorCode.DIALOG_ROW_BUTTON_LIMIT_REACHED,
            )

    seen: set[tuple[int, int]] = set()
    for button in buttons:
        position = (button.row, button.column)
        if position in seen:
            raise ValidationError(
                f"Two buttons at row {button.row}, column {button.column} in '{window_key}'",
                code=ErrorCode.DIALOG_BUTTON_POSITION_TAKEN,
            )
        seen.add(position)
        if not catalog.is_editable_text_key(button.text_key):
            # A button's text_key is what dialog_text_keys() lets import write to
            # in bot_translations. Deriving that allowlist from stored rows means
            # an unvalidated text_key here authorizes a write to any translation
            # row -- bot command descriptions, notifications -- so the bound
            # belongs at the boundary every write path already passes through.
            raise ValidationError(
                f"'{button.text_key}' is not an editable dialog text key",
                code=ErrorCode.DIALOG_TEXT_KEY_NOT_EDITABLE,
            )
        if button.is_hidden and button.text_key in system_text_keys:
            raise ValidationError(
                f"System button '{button.text_key}' cannot be hidden",
                code=ErrorCode.DIALOG_SYSTEM_BUTTON_NOT_HIDEABLE,
            )
        _validate_button(button, window_kind, navigable, seed_actions)


def _validate_button(
    button: DialogButtonInputDto,
    window_kind: DialogWindowKind,
    navigable: set[str],
    seed_actions: set[str],
) -> None:
    if button.visibility_condition and button.visibility_condition not in catalog.condition_keys():
        raise ValidationError(
            f"Unknown visibility condition: {button.visibility_condition}",
            code=ErrorCode.DIALOG_VISIBILITY_UNKNOWN,
        )
    if button.link_type == ButtonLinkType.ACTION:
        if window_kind == DialogWindowKind.CUSTOM:
            raise ValidationError(
                "Custom windows cannot bind action buttons",
                code=ErrorCode.DIALOG_CUSTOM_WINDOW_ACTION,
            )
        if button.action_key not in catalog.action_keys():
            raise ValidationError(
                f"Unknown action: {button.action_key}", code=ErrorCode.DIALOG_ACTION_UNKNOWN
            )
        if button.action_key not in seed_actions:
            raise ValidationError(
                f"Action '{button.action_key}' is not one of this window's actions",
                code=ErrorCode.DIALOG_ACTION_NOT_IN_WINDOW,
            )
    elif button.link_type == ButtonLinkType.NAVIGATE:
        if button.target_window_key not in navigable:
            raise ValidationError(
                f"Unknown target window: {button.target_window_key}",
                code=ErrorCode.DIALOG_TARGET_WINDOW_UNKNOWN,
            )
    elif button.link_type == ButtonLinkType.URL:
        if not button.url_value:
            raise ValidationError(
                "URL button needs a url_value", code=ErrorCode.DIALOG_BUTTON_URL_MISSING
            )
        validate_url_value(button.url_value)
