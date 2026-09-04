from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Optional

from app.core.enums import BannerName, ButtonLinkType, ButtonStyleKind, DialogFlow

Resolver = Callable[..., object]


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
    icon_custom_emoji_id: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class CatalogWindow:
    key: str
    flow: DialogFlow
    text_keys: tuple[str, ...]
    banner_name: Optional[BannerName]
    buttons: tuple[CatalogButton, ...] = ()


_WINDOWS: Final[dict[str, CatalogWindow]] = {}
_ACTIONS: Final[dict[str, Resolver]] = {}
_CONDITIONS: Final[dict[str, Resolver]] = {}
_VARIABLES: Final[dict[str, Resolver]] = {}


def _register(registry: dict[str, object], key: str, value: object, label: str) -> None:
    if key in registry:
        raise ValueError(f"Duplicate {label} key: {key}")
    registry[key] = value


def register_window(window: CatalogWindow) -> None:
    _register(_WINDOWS, window.key, window, "window")  # type: ignore[arg-type]


def register_action(key: str, handler: Resolver) -> None:
    _register(_ACTIONS, key, handler, "action")  # type: ignore[arg-type]


def register_condition(key: str, resolver: Resolver) -> None:
    _register(_CONDITIONS, key, resolver, "condition")  # type: ignore[arg-type]


def register_variable(key: str, resolver: Resolver) -> None:
    _register(_VARIABLES, key, resolver, "variable")  # type: ignore[arg-type]


def all_windows() -> tuple[CatalogWindow, ...]:
    return tuple(_WINDOWS.values())


def has_window(key: str) -> bool:
    return key in _WINDOWS


def get_window(key: str) -> CatalogWindow:
    return _WINDOWS[key]


def action_keys() -> frozenset[str]:
    return frozenset(_ACTIONS)


def condition_keys() -> frozenset[str]:
    return frozenset(_CONDITIONS)


def variable_keys() -> frozenset[str]:
    return frozenset(_VARIABLES)


def get_action(key: str) -> Resolver:
    return _ACTIONS[key]


def get_condition(key: str) -> Resolver:
    return _CONDITIONS[key]


def window_snapshot(key: str) -> dict:
    window = _WINDOWS[key]
    return {
        "banner_name": window.banner_name.value if window.banner_name else None,
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
                "icon_custom_emoji_id": b.icon_custom_emoji_id,
                "is_hidden": False,
            }
            for b in window.buttons
        ],
    }


def _reset_for_tests() -> None:
    # test-only: flow catalog modules register at import time and are never unregistered in prod
    _WINDOWS.clear()
    _ACTIONS.clear()
    _CONDITIONS.clear()
    _VARIABLES.clear()
