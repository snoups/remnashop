import logging
import re
from typing import Any, Final, Optional

from fluentogram import TranslatorRunner

from app.modules.dialogs import catalog
from app.telegram.dialogs.config_cache import DialogConfigCache

logger = logging.getLogger(__name__)

_VARIABLE_RE: Final[re.Pattern[str]] = re.compile(r"\$\{([a-z0-9_.]+)\}")


def _resolve_variables(value: Optional[str], getter_data: dict[str, Any]) -> Optional[str]:
    if value is None:
        return None

    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key not in catalog.variable_keys():
            logger.warning("Unknown dialog variable token: %s", key)
            return ""
        return str(catalog.get_variable(key)(getter_data))

    return _VARIABLE_RE.sub(_sub, value)


def resolve_variable_kwargs(getter_data: dict[str, Any]) -> dict[str, object]:
    """Resolve every registered catalog variable against this render's getter
    data, for use as **kwargs into a fluentogram runner.get(...) call -- lets
    window text and button labels use real Fluent `{ $var }` syntax for any
    catalog-registered variable, the same set url_value's own ${var} token
    substitution already draws from.
    """
    return {key: catalog.get_variable(key)(getter_data) for key in catalog.variable_keys()}


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
                logger.warning("Unknown dialog condition: %s", button.visibility_condition)
                continue
            condition = catalog.get_condition(button.visibility_condition)
            if not condition(getter_data):
                continue
        rows.setdefault(button.row, []).append(
            {
                "id": button.id,
                "text": runner.get(button.text_key, **variable_kwargs),
                "style": button.style,
                "icon_custom_emoji_id": button.icon_custom_emoji_id,
                "link_type": button.link_type,
                "action_key": button.action_key,
                "target_window_key": button.target_window_key,
                "url_value": _resolve_variables(button.url_value, getter_data),
            }
        )
    return [rows[row] for row in sorted(rows)]
