import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Optional

from app.core.enums import ButtonLinkType, ButtonStyleKind, DialogFlow

Resolver = Callable[..., object]

# Fluent identifiers can't contain dots. A dotted catalog key works only in
# url_value's own ${var} substitution, so it's left out of what Fluent text
# is offered.
_FLUENT_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")

# A url_value may interpolate catalog variables as ${name}; what's left after
# stripping those tokens is the literal part of the URL. Telegram rejects the
# whole keyboard, and the window with it, if a button URL has another scheme.
URL_VARIABLE_RE: Final[re.Pattern[str]] = re.compile(r"\$\{([a-z0-9_.]+)\}")
URL_SCHEMES: Final[tuple[str, ...]] = ("https://", "http://", "tg://")

# The namespace for admin-authored dialog text that has no catalog registration
# of its own: a custom window's body, or a freshly-added button's label.
# Dashes, not dots: a dot reads as a message attribute
# (translations.serializer.split_message_key).
CUSTOM_TEXT_KEY_PREFIX: Final[str] = "msg-dialog-custom-"
# The key becomes a Fluent message id verbatim, so anything outside this would
# let one button's label define or shadow another message in the locale.
_CUSTOM_TEXT_KEY_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9-]+")

# A button's icon is a translation of its own, so it can differ per locale and
# never gets mixed into the label text. Exactly one of the two is ever filled:
# the plain glyph goes into the button's text, the premium id into Telegram's
# icon_custom_emoji_id.
ICON_KEY_SUFFIX: Final[str] = "-icon"
ICON_ID_KEY_SUFFIX: Final[str] = "-icon-id"

# A custom window's body key is this prefix plus the window key.
_WINDOW_TEXT_KEY_PREFIX: Final[str] = "msg-dialog-"

# Premium emoji in window text: the glyph plus the custom emoji id, turned into a
# <tg-emoji> tag at render time.
PREMIUM_EMOJI_RE: Final[re.Pattern[str]] = re.compile(r"\[([^\[\]]{1,16})\]\(emoji:(\d{1,24})\)")


@dataclass(frozen=True, kw_only=True)
class CatalogButton:
    key: str
    text_key: str
    link_type: ButtonLinkType
    row: int = 0
    column: int = 0
    action_key: Optional[str] = None
    target_window_key: Optional[str] = None
    url_value: Optional[str] = None
    visibility_condition: Optional[str] = None
    style: Optional[ButtonStyleKind] = None


@dataclass(frozen=True, kw_only=True)
class CatalogWindow:
    key: str
    flow: DialogFlow
    text_keys: tuple[str, ...]
    banner_name: Optional[str]
    buttons: tuple[CatalogButton, ...] = ()
    # passed by this window's own getter (e.g. a device count), on top of the
    # global variables every text may use
    text_variables: tuple[str, ...] = ()


_WINDOWS: Final[dict[str, CatalogWindow]] = {}
_ACTION_KEYS: Final[set[str]] = set()
_ACTIONS: Final[dict[str, Resolver]] = {}
_CONDITIONS: Final[dict[str, Resolver]] = {}
_VARIABLES: Final[dict[str, Resolver]] = {}
# variable -> the group the editor's picker lists it under ("user", "subscription", ...)
_VARIABLE_CATEGORIES: Final[dict[str, str]] = {}


def _register(registry: dict[str, object], key: str, value: object, label: str) -> None:
    if key in registry:
        raise ValueError(f"Duplicate {label} key: {key}")
    registry[key] = value


def register_window(window: CatalogWindow) -> None:
    _register(_WINDOWS, window.key, window, "window")  # type: ignore[arg-type]


def register_action_key(key: str) -> None:
    if key in _ACTION_KEYS:
        raise ValueError(f"Duplicate action key: {key}")
    _ACTION_KEYS.add(key)


def bind_action_handler(key: str, handler: Resolver) -> None:
    # the key must be declared via register_action_key first, so validation
    # (also in the api process, which binds no handlers) knows every action,
    # not just the ones some button happens to mention
    if key not in _ACTION_KEYS:
        raise ValueError(f"Cannot bind handler to unregistered action key: {key}")
    if key in _ACTIONS:
        raise ValueError(f"Action handler already bound: {key}")
    _ACTIONS[key] = handler


def register_condition(key: str, resolver: Resolver) -> None:
    _register(_CONDITIONS, key, resolver, "condition")  # type: ignore[arg-type]


_RESERVED_VARIABLE_NAMES: Final[frozenset[str]] = frozenset({"key", "self"})


def register_variable(key: str, resolver: Resolver, *, category: str) -> None:
    # Named <category>_<field> (user_name, not name): a bare field name is
    # ambiguous once more than one thing in the bot has it.
    if key in _RESERVED_VARIABLE_NAMES:
        # These collide with runner.get(key, **kwargs)'s own positional params
        # -> "got multiple values for argument" at render time.
        raise ValueError(f"Reserved variable name: {key}")
    _register(_VARIABLES, key, resolver, "variable")  # type: ignore[arg-type]
    _VARIABLE_CATEGORIES[key] = category


def all_windows() -> tuple[CatalogWindow, ...]:
    return tuple(_WINDOWS.values())


def has_window(key: str) -> bool:
    return key in _WINDOWS


def get_window(key: str) -> CatalogWindow:
    return _WINDOWS[key]


def window_text_keys(window_key: str) -> tuple[str, ...]:
    # A custom window isn't in the in-process catalog; its body follows the fixed
    # naming convention create_custom_window.py generates.
    window = _WINDOWS.get(window_key)
    return window.text_keys if window is not None else (f"{_WINDOW_TEXT_KEY_PREFIX}{window_key}",)


def window_key_for_text_key(text_key: str) -> Optional[str]:
    """The window whose body this key would be. For a custom-prefixed key that
    is only a candidate: a button label shares the prefix, so the caller
    confirms the window exists."""
    for window in _WINDOWS.values():
        if text_key in window.text_keys:
            return window.key
    if text_key.startswith(CUSTOM_TEXT_KEY_PREFIX):
        return text_key.removeprefix(_WINDOW_TEXT_KEY_PREFIX)
    return None


def has_action_handler(key: str) -> bool:
    return key in _ACTIONS


def action_keys() -> frozenset[str]:
    return frozenset(_ACTION_KEYS)


def condition_keys() -> frozenset[str]:
    return frozenset(_CONDITIONS)


def variable_keys() -> frozenset[str]:
    return frozenset(_VARIABLES)


def variable_categories() -> dict[str, str]:
    return dict(_VARIABLE_CATEGORIES)


def text_variable_keys() -> frozenset[str]:
    return frozenset(key for key in _VARIABLES if _FLUENT_IDENTIFIER_RE.match(key))


def text_keys() -> frozenset[str]:
    # Every text key a catalog-registered window or button genuinely owns.
    # Custom windows aren't in the in-process catalog, hence the prefix check
    # callers layer on top of this set.
    keys: set[str] = set()
    for window in _WINDOWS.values():
        keys.update(window.text_keys)
        keys.update(button.text_key for button in window.buttons)
    return frozenset(keys)


def icon_text_key(text_key: str) -> str:
    return f"{text_key}{ICON_KEY_SUFFIX}"


def icon_id_text_key(text_key: str) -> str:
    return f"{text_key}{ICON_ID_KEY_SUFFIX}"


def is_icon_text_key(key: str) -> bool:
    return key.endswith((ICON_KEY_SUFFIX, ICON_ID_KEY_SUFFIX))


def is_editable_text_key(key: str) -> bool:
    # An icon key is editable exactly when the label it belongs to is.
    base = key.removesuffix(ICON_ID_KEY_SUFFIX).removesuffix(ICON_KEY_SUFFIX)
    if base in text_keys():
        return True
    suffix = base.removeprefix(CUSTOM_TEXT_KEY_PREFIX)
    return suffix != base and _CUSTOM_TEXT_KEY_SUFFIX_RE.fullmatch(suffix) is not None


def get_action(key: str) -> Resolver:
    return _ACTIONS[key]


def get_condition(key: str) -> Resolver:
    return _CONDITIONS[key]


def get_variable(key: str) -> Resolver:
    return _VARIABLES[key]


def window_snapshot(key: str) -> dict:
    window = _WINDOWS[key]
    return {
        "banner_name": window.banner_name,
        "buttons": [
            {
                "key": b.key,
                "text_key": b.text_key,
                "row": b.row,
                "column": b.column,
                "link_type": b.link_type.value,
                "action_key": b.action_key,
                "target_window_key": b.target_window_key,
                "url_value": b.url_value,
                "visibility_condition": b.visibility_condition,
                "style": b.style.value if b.style else None,
                "is_hidden": False,
            }
            for b in window.buttons
        ],
    }


def _reset_for_tests() -> None:
    # test-only: flow catalog modules register at import time and are never unregistered in prod
    _WINDOWS.clear()
    _ACTION_KEYS.clear()
    _ACTIONS.clear()
    _CONDITIONS.clear()
    _VARIABLES.clear()
    _VARIABLE_CATEGORIES.clear()
