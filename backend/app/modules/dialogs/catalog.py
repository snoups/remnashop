import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Optional

from app.core.enums import ButtonLinkType, ButtonStyleKind, DialogFlow

Resolver = Callable[..., object]

# Fluent variable identifiers are plain identifiers -- no dots. The catalog's
# own dotted keys (e.g. "subscription.url") are only ever used by the render
# engine's own ${var} substitution in url_value, which is unrelated to Fluent
# and has no such restriction; this filters them out of what's offered for use
# inside real Fluent `{ $var }` text.
_FLUENT_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")

# A url_value may interpolate catalog variables as ${name}; what's left after
# stripping those tokens is the literal part of the URL, and Telegram only
# accepts a keyboard whose button URLs carry one of these schemes -- it rejects
# the whole keyboard otherwise, taking the window down with it.
URL_VARIABLE_RE: Final[re.Pattern[str]] = re.compile(r"\$\{([a-z0-9_.]+)\}")
URL_SCHEMES: Final[tuple[str, ...]] = ("https://", "http://", "tg://")

# The namespace for admin-authored dialog text that has no catalog registration
# of its own: a custom window's body, or a freshly-added button's label. Must
# stay dash-separated, not dot-separated -- see create_custom_window.py's key
# generation for why a dot here fails Fluent's identifier grammar.
CUSTOM_TEXT_KEY_PREFIX: Final[str] = "msg-dialog-custom-"

# A button's icon is a translation of its own, so it can differ per locale and
# never gets mixed into the label text. Exactly one of the two is ever filled:
# the plain glyph goes into the button's text, the premium id into Telegram's
# icon_custom_emoji_id.
ICON_KEY_SUFFIX: Final[str] = "-icon"
ICON_ID_KEY_SUFFIX: Final[str] = "-icon-id"


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


_WINDOWS: Final[dict[str, CatalogWindow]] = {}
_ACTION_KEYS: Final[set[str]] = set()
_ACTIONS: Final[dict[str, Resolver]] = {}
_CONDITIONS: Final[dict[str, Resolver]] = {}
_VARIABLES: Final[dict[str, Resolver]] = {}


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
    # Requires the key to already be declared via register_action_key -- this is
    # what lets an action be a deliberately-declared thing usable for validation
    # (e.g. from the api process, which never binds a handler) rather than
    # something that becomes valid merely because some window's button mentions it.
    if key not in _ACTION_KEYS:
        raise ValueError(f"Cannot bind handler to unregistered action key: {key}")
    if key in _ACTIONS:
        raise ValueError(f"Action handler already bound: {key}")
    _ACTIONS[key] = handler


def register_condition(key: str, resolver: Resolver) -> None:
    _register(_CONDITIONS, key, resolver, "condition")  # type: ignore[arg-type]


_RESERVED_VARIABLE_NAMES: Final[frozenset[str]] = frozenset({"key", "self"})


def register_variable(key: str, resolver: Resolver) -> None:
    if key in _RESERVED_VARIABLE_NAMES:
        # These collide with runner.get(key, **kwargs)'s own positional params
        # -> "got multiple values for argument" at render time.
        raise ValueError(f"Reserved variable name: {key}")
    _register(_VARIABLES, key, resolver, "variable")  # type: ignore[arg-type]


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
    return window.text_keys if window is not None else (f"msg-dialog-{window_key}",)


def has_action_handler(key: str) -> bool:
    return key in _ACTIONS


def action_keys() -> frozenset[str]:
    return frozenset(_ACTION_KEYS)


def condition_keys() -> frozenset[str]:
    return frozenset(_CONDITIONS)


def variable_keys() -> frozenset[str]:
    return frozenset(_VARIABLES)


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


def is_editable_text_key(key: str) -> bool:
    # An icon key is editable exactly when the label it belongs to is.
    base = key.removesuffix(ICON_ID_KEY_SUFFIX).removesuffix(ICON_KEY_SUFFIX)
    return base in text_keys() or base.startswith(CUSTOM_TEXT_KEY_PREFIX)


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
