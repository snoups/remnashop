from decimal import Decimal
from typing import Any, Final, Union

import orjson
from pydantic import SecretStr

_ENCODE_OPTIONS: Final[int] = orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS


def json_default(obj: Any) -> Any:
    if isinstance(obj, SecretStr):
        return obj.get_secret_value()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type '{type(obj).__name__}' is not JSON serializable")


def encode(data: Any) -> bytes:
    return orjson.dumps(data, default=json_default, option=_ENCODE_OPTIONS)


def decode(data: Union[str, bytes]) -> Any:
    return orjson.loads(data)
