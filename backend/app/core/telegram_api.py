from typing import Any, Final

_API_URL: Final[str] = "https://api.telegram.org"
_DEFAULT_RETRY_AFTER_S: Final[float] = 1.0


def bot_method_url(token: str, method: str) -> str:
    return f"{_API_URL}/bot{token}/{method}"


def bot_file_url(token: str, file_path: str) -> str:
    return f"{_API_URL}/file/bot{token}/{file_path}"


def retry_after_seconds(payload: dict[str, Any]) -> float:
    # a 429 carries parameters.retry_after; anything malformed waits the default
    parameters = payload.get("parameters")
    value: Any = parameters.get("retry_after") if isinstance(parameters, dict) else None
    try:
        return float(value)
    except (TypeError, ValueError):
        return _DEFAULT_RETRY_AFTER_S
