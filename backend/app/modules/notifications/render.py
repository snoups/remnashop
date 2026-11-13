import html
import re
from collections.abc import Sequence
from typing import Any, Final, Optional, Union

from fluent_compiler.bundle import FluentBundle
from loguru import logger

from app.core.enums import Locale

# rendered by the test push; message_id() turns it into ntf-test
TEST_EVENT_TYPE: Final[str] = "Test"
_CAMEL_BOUNDARY: Final[re.Pattern[str]] = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)
_USER_KEYS: Final[tuple[str, ...]] = ("user", "target", "actor")
_EMPTY: Final[str] = "—"
_NON_WORD: Final[re.Pattern[str]] = re.compile(r"\W")


def message_id(event_type: str) -> str:
    # one word, not O + Auth
    name = event_type.removesuffix("Event").replace("OAuth", "Oauth")
    return "ntf-" + _CAMEL_BOUNDARY.sub("-", name).lower()


def _display(snapshot: dict[str, Any]) -> str:
    if snapshot.get("login"):
        return str(snapshot["login"])
    if snapshot.get("username"):
        return f"@{snapshot['username']}"
    return str(snapshot.get("name") or _EMPTY)


# (label, value, monospace)
CardRow = tuple[str, str, bool]
# (icon, heading, rows)
CardBlock = tuple[str, str, Sequence[CardRow]]


def telegram_card(
    title: str,
    body: str,
    *,
    emoji: str,
    hashtag: Optional[str] = None,
    blocks: Sequence[CardBlock] = (),
    quote: Optional[str] = None,
    footer: Optional[str] = None,
) -> str:
    """A notification as Telegram HTML: a bold heading, the text in a quote,
    "label: value" blocks, a closing quote and a plain footer; every rendered
    string is escaped here, so user-controlled values in a payload stay text.
    Empty rows and blocks left without rows are dropped."""
    lines: list[str] = []
    if hashtag:
        lines += [f"#{_NON_WORD.sub('', hashtag)}", ""]
    lines.append(f"<b>{html.escape(f'{emoji} {title}'.strip())}</b>")
    if body:
        lines += ["", f"<blockquote>{html.escape(body)}</blockquote>"]
    for icon, heading, rows in blocks:
        shown = [
            f"• <b>{html.escape(label)}</b>: "
            + (f"<code>{html.escape(value)}</code>" if code else html.escape(value))
            for label, value, code in rows
            if value
        ]
        if shown:
            lines += [
                "",
                f"{html.escape(icon)} <b>{html.escape(heading)}</b>:".lstrip(),
                f"<blockquote>{chr(10).join(shown)}</blockquote>",
            ]
    if quote:
        lines += ["", f"<blockquote>{html.escape(quote)}</blockquote>"]
    if footer:
        lines += ["", f"<i>{html.escape(footer)}</i>"]
    return "\n".join(lines)


def notification_args(
    payload: dict[str, Any], ip_address: Optional[str]
) -> dict[str, Union[str, int]]:
    args: dict[str, Union[str, int]] = {
        # a flag reads as a selector: { $is_trial -> [yes] ... }
        key: ("yes" if value else "no") if isinstance(value, bool) else value
        for key, value in payload.items()
        if isinstance(value, (str, int))
    }
    for key in _USER_KEYS:
        snapshot = payload.get(key)
        if isinstance(snapshot, dict):
            args[key] = _display(snapshot)
    # templates print it unconditionally; without it Fluent would print "ip"
    args["ip"] = ip_address or _EMPTY
    return args


class NotificationRenderer:
    def __init__(self, fluent_by_locale: dict[Locale, str], default_locale: Locale) -> None:
        self._bundles = {
            locale: FluentBundle.from_string(  # type: ignore[no-untyped-call]
                locale.value, text, use_isolating=False
            )
            for locale, text in fluent_by_locale.items()
        }
        self._default_locale = default_locale

    def render(
        self, locale: Locale, event_type: str, args: dict[str, Union[str, int]]
    ) -> tuple[str, str]:
        if event_type.startswith(("RecurringPayment", "CustomerRecurringPayment")):
            reason_args = {**args, "reason": str(args.get("reason", "unknown"))}
            args = {
                **args,
                "reason_text": self.text(locale, "ntf-recurring-reason", reason_args) or _EMPTY,
            }
        key = message_id(event_type)
        for candidate in (locale, self._default_locale):
            bundle = self._bundles.get(candidate)
            if bundle is None or not bundle.has_message(key):
                continue
            try:
                title, title_errors = bundle.format(f"{key}.title", args)
                body, body_errors = bundle.format(key, args)
            except KeyError:
                # a message saved without its .title in the translations editor
                logger.warning(f"Notification template '{key}' ({candidate}) has no title")
                continue
            for error in [*title_errors, *body_errors]:
                logger.warning(f"Notification template '{key}' ({candidate}): {error}")
            return str(title), str(body)
        return event_type, ""

    def render_message(self, locale: Locale, key: str, args: dict[str, Union[str, int]]) -> str:
        for candidate in (locale, self._default_locale):
            bundle = self._bundles.get(candidate)
            if bundle is None or not bundle.has_message(key):
                continue
            value, errors = bundle.format(key, args)
            for error in errors:
                logger.warning(f"Template '{key}' ({candidate}): {error}")
            return str(value)
        return ""

    def emoji(
        self,
        locale: Locale,
        event_type: str,
        args: Optional[dict[str, Union[str, int]]] = None,
    ) -> Optional[str]:
        return self.text(locale, f"{message_id(event_type)}.emoji", args)

    def text(
        self, locale: Locale, key: str, args: Optional[dict[str, Union[str, int]]] = None
    ) -> Optional[str]:
        for candidate in (locale, self._default_locale):
            bundle = self._bundles.get(candidate)
            if bundle is None:
                continue
            try:
                # has_message() is False for a message that has only attributes
                value, errors = bundle.format(key, args or {})
            except KeyError:
                continue
            for error in errors:
                logger.warning(f"Template '{key}' ({candidate}): {error}")
            return str(value)
        return None
