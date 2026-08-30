from decimal import Decimal
from typing import Any, Callable, Optional, Union

import orjson
from aiogram.types import InlineKeyboardMarkup
from pydantic import SecretStr, TypeAdapter


def encode(data: Any) -> bytes:
    return orjson.dumps(
        data,
        default=_default_processor,
        option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS,
    )


def decode(data: Union[str, bytes]) -> Any:
    return orjson.loads(data)


def bytes_encode(data: Any) -> bytes:
    return encode(data)


def _default_processor(obj: Any) -> Any:
    if isinstance(obj, SecretStr):
        return obj.get_secret_value()
    if isinstance(obj, InlineKeyboardMarkup):
        return obj.model_dump()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type '{type(obj).__name__}' is not JSON serializable")


def _reveal_secrets(
    python_value: Any,
    json_value: Any,
    encrypt: Optional[Callable[[str], str]],
) -> Any:
    if isinstance(python_value, SecretStr):
        raw = python_value.get_secret_value()
        return encrypt(raw) if encrypt is not None else raw
    if isinstance(python_value, dict) and isinstance(json_value, dict):
        return {
            jk: _reveal_secrets(pv, jv, encrypt)
            for (_pk, pv), (jk, jv) in zip(python_value.items(), json_value.items())
        }
    if isinstance(python_value, list) and isinstance(json_value, list):
        return [_reveal_secrets(pv, jv, encrypt) for pv, jv in zip(python_value, json_value)]
    return json_value


def dump_json_safe(value: Any, type_: Any, encrypt: Optional[Callable[[str], str]] = None) -> Any:
    """Like `TypeAdapter(type_).dump_python(value, mode="json")`, but `SecretStr` fields
    keep their real value (or `encrypt(value)`) instead of pydantic's "**********" mask.
    Never dump with mode="json" directly on anything that might contain a SecretStr."""
    adapter: TypeAdapter[Any] = TypeAdapter(type_)
    python_dump = adapter.dump_python(value, mode="python")
    json_dump = adapter.dump_python(value, mode="json")
    return _reveal_secrets(python_dump, json_dump, encrypt)
