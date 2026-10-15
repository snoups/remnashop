from typing import Final

from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogWindowDto

# Bumped when the payload's meaning changes: banner_name went from a fixed
# category to a free name, and a button's icon moved out into translations.
# An older file would import cleanly and land wrong, so it is refused instead.
EXPORT_VERSION: Final[int] = 2


def dialog_text_keys(windows: list[DialogWindowDto]) -> set[str]:
    keys: set[str] = set()
    for window in windows:
        keys.update(catalog.window_text_keys(window.key))
        keys.update(button.text_key for button in window.buttons)
    return keys
