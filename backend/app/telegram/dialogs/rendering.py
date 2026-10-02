import html
import re
from typing import Any, Optional

from fluentogram import TranslatorRunner
from fluentogram.exceptions import KeyNotFoundError
from loguru import logger

from app.modules.dialogs import catalog
from app.modules.translations import strip_serializer_escapes
from app.telegram.dialogs.config_cache import DialogConfigCache


def render_window_text(runner: TranslatorRunner, key: str, **kwargs: Any) -> str:
    # Premium emoji in window text needs the glyph in the message plus a
    # custom_emoji entity over it, and aiogram-dialog's NewMessage carries no
    # entities -- so the window renders as HTML and the markup becomes a
    # <tg-emoji> tag. Everything else is escaped first, which is what keeps a
    # variable resolving to "<b>" literal instead of turning into formatting.
    escaped = html.escape(strip_serializer_escapes(runner.get(key, **kwargs)), quote=False)
    return catalog.PREMIUM_EMOJI_RE.sub(r'<tg-emoji emoji-id="\2">\1</tg-emoji>', escaped)


def _resolve_variables(value: Optional[str], getter_data: dict[str, Any]) -> Optional[str]:
    if value is None:
        return None

    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key not in catalog.variable_keys():
            logger.warning(f"Unknown dialog variable token: {key}")
            return ""
        return str(catalog.get_variable(key)(getter_data))

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
    """Resolve every registered catalog variable against this render's getter
    data, for use as **kwargs into a fluentogram runner.get(...) call -- lets
    window text and button labels use real Fluent `{ $var }` syntax for any
    catalog-registered variable, the same set url_value's own ${var} token
    substitution already draws from.
    """
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
