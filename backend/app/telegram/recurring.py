from typing import Final

# A 128-bit prefix leaves room for the widget and dialog IDs in a 64-byte callback.
_CALLBACK_PREFIX_LENGTH: Final[int] = 16


def consent_callback_id(terms_id: str) -> str:
    return terms_id[:_CALLBACK_PREFIX_LENGTH]
