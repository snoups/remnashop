import html
import re
from typing import Any, Final, Optional, TypeVar
from urllib.parse import quote

from fluentogram import TranslatorRunner
from fluentogram.exceptions import KeyNotFoundError
from loguru import logger

from app.core.utils.telegram_text import (
    PREMIUM_EMOJI_RE,
    TELEGRAM_CAPTION_LIMIT,
    html_text_length,
)
from app.modules.dialogs import catalog
from app.modules.translations import strip_serializer_escapes
from app.telegram.dialogs.config_cache import DialogConfigCache

_T = TypeVar("_T")


class TrustedHtml(str):
    """Markup render_window_text inserts unescaped: blocks built from ftl fragments."""


# sentinels no translation or escaped value contains: _EMPTY marks lines to
# drop, _VALUE_NEWLINE hides a value's own line breaks so the rule sees only
# template lines and a multi-line block is kept or dropped whole
_EMPTY: Final[str] = "\x00empty\x00"
_VALUE_NEWLINE: Final[str] = "\x00nl\x00"
_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^<>]*>")
_BLANK_RUN_RE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")


def _prepare_value(value: Any) -> Any:
    if value is None or value == "":
        return _EMPTY
    if isinstance(value, TrustedHtml):
        return value.replace("\n", _VALUE_NEWLINE)
    if isinstance(value, str):
        # quotes for a value inside an attribute; "[" keeps a value from forming
        # premium-emoji markup, which only the template may use
        escaped = html.escape(value, quote=False).replace('"', "&quot;").replace("'", "&#39;")
        return escaped.replace("[", "&#91;").replace("\n", _VALUE_NEWLINE)
    return value


def _drop_empty_lines(text: str) -> str:
    # A dropped line keeps its tags, or a `</blockquote>` on it would leave the
    # message unbalanced and Telegram would reject it. Values are escaped by now,
    # so every raw `<` belongs to the template or a balanced TrustedHtml block.
    # A pair opened and closed on the dropped line goes with it.
    kept: list[str] = []
    pending = ""
    for line in text.split("\n"):
        if _EMPTY not in line:
            kept.append(pending + line)
            pending = ""
            continue
        opened: list[str] = []
        for tag in _TAG_RE.findall(line):
            if not tag.startswith("</"):
                opened.append(tag)
            elif opened:
                opened.pop()
            elif kept and not pending:
                kept[-1] += tag
            else:
                pending += tag
        pending += "".join(opened)
    if pending:
        if kept:
            kept[-1] += pending
        else:
            kept.append(pending)
    return _BLANK_RUN_RE.sub("\n\n", "\n".join(kept)).strip("\n")


def render_window_text(runner: TranslatorRunner, key: str, **kwargs: Any) -> str:
    # Rendered as HTML: the template is admin-edited markup, values are escaped
    # so a user's display name holding "<b>" stays literal.
    prepared = {name: _prepare_value(value) for name, value in kwargs.items()}
    text = _drop_empty_lines(strip_serializer_escapes(runner.get(key, **prepared)))
    if html_text_length(text) == 0:
        # Telegram refuses an empty message, so the lines stay with their values empty
        prepared = {name: "" if value == _EMPTY else value for name, value in prepared.items()}
        text = strip_serializer_escapes(runner.get(key, **prepared))
    text = text.replace(_VALUE_NEWLINE, "\n")
    return PREMIUM_EMOJI_RE.sub(r'<tg-emoji emoji-id="\2">\1</tg-emoji>', text)


def fits_caption(text: str) -> bool:
    return html_text_length(text) <= TELEGRAM_CAPTION_LIMIT


def banner_within_caption(banner: Optional[_T], text: str) -> Optional[_T]:
    """The banner to send with a rendered text, or None when the text is too
    long for a caption and has to go out as a plain message."""
    if banner is None or fits_caption(text):
        return banner
    logger.warning(f"Window text exceeds the caption limit, sending without banner: {banner}")
    return None


def _resolve_variables(value: Optional[str], getter_data: dict[str, Any]) -> Optional[str]:
    if value is None:
        return None

    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key not in catalog.variable_keys():
            logger.warning(f"Unknown dialog variable token: {key}")
            return ""
        resolved = str(catalog.get_variable(key)(getter_data))
        # a variable opening the URL is the URL itself; inside one it's a part of it
        return resolved if match.start() == 0 else quote(resolved, safe="")

    return catalog.URL_VARIABLE_RE.sub(_sub, value)


def _optional_translation(runner: TranslatorRunner, key: str) -> Optional[str]:
    # Most buttons carry no icon at all, and fluentogram raises on a key that was
    # never seeded rather than returning nothing.
    try:
        value = runner.get(key)
    except KeyNotFoundError:
        return None
    return strip_serializer_escapes(value).strip() or None


def resolve_variable_kwargs(getter_data: dict[str, Any]) -> dict[str, object]:
    """Every catalog variable resolved against this render's getter data, as
    runner.get() kwargs: window texts and labels get the same `{ $var }` set
    that url_value's ${var} substitution draws from."""
    return {key: catalog.get_variable(key)(getter_data) for key in catalog.variable_keys()}


def label_with_icon(runner: TranslatorRunner, text_key: str) -> str:
    """A label for a button the bot hardcodes rather than renders from config.
    Those never reach ConfigKeyboard, so the icon has to be glued on here or it
    would silently never show."""
    label = runner.get(text_key)
    icon = _optional_translation(runner, catalog.icon_text_key(text_key))
    return f"{icon} {label}" if icon else label


async def render_dialog_buttons(
    window_key: str,
    cache: DialogConfigCache,
    runner: TranslatorRunner,
    getter_data: dict[str, Any],
) -> list[list[dict[str, Any]]]:
    window = await cache.get_window(window_key)
    variable_kwargs = resolve_variable_kwargs(getter_data)
    rows: dict[int, list[dict[str, Any]]] = {}
    for button in window.buttons:
        if button.is_hidden:
            continue
        if button.visibility_condition:
            if button.visibility_condition not in catalog.condition_keys():
                logger.warning(f"Unknown dialog condition: {button.visibility_condition}")
                continue
            condition = catalog.get_condition(button.visibility_condition)
            if not condition(getter_data):
                continue
        rows.setdefault(button.row, []).append(
            {
                "id": button.id,
                "text": runner.get(button.text_key, **variable_kwargs),
                "style": button.style,
                "icon": _optional_translation(runner, catalog.icon_text_key(button.text_key)),
                "icon_custom_emoji_id": _optional_translation(
                    runner, catalog.icon_id_text_key(button.text_key)
                ),
                "link_type": button.link_type,
                "action_key": button.action_key,
                "target_window_key": button.target_window_key,
                "url_value": _resolve_variables(button.url_value, getter_data),
            }
        )
    return [rows[row] for row in sorted(rows)]
