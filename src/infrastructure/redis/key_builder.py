from abc import ABC
from dataclasses import dataclass, fields
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Self
from uuid import UUID

from loguru import logger
from pydantic import SecretStr


@dataclass(frozen=True)
class StorageKey(ABC):
    if TYPE_CHECKING:
        __separator__: ClassVar[str]
        __prefix__: ClassVar[Optional[str]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.__separator__ = kwargs.pop("separator", ":")
        cls.__prefix__ = kwargs.pop("prefix", None)
        prefix_val = cls.__prefix__ or ""

        if cls.__separator__ in prefix_val:
            logger.error(f"Separator '{cls.__separator__}' found in prefix '{prefix_val}'")
            raise ValueError("Separator cannot be used inside prefix")

        super().__init_subclass__(**kwargs)

    @classmethod
    def from_obj(cls, obj: Any) -> Self:
        data = {}

        for field in fields(cls):
            val = getattr(obj, field.name, None)

            if val is not None:
                data[field.name] = val

        return cls(**data)


def serialize_storage_key(key_obj: StorageKey) -> str:
    cls = key_obj.__class__
    parts = [cls.__prefix__] if cls.__prefix__ else []
    sorted_fields = sorted(fields(key_obj), key=lambda f: f.name)

    for field in sorted_fields:
        val = getattr(key_obj, field.name)
        encoded = encode_storage_value(val)

        if cls.__separator__ in encoded:
            logger.error(f"Separator '{cls.__separator__}' found in value of '{field.name}'")
            raise ValueError("Separator symbol cannot be used in value")

        parts.append(encoded)

    return cls.__separator__.join(parts)


def encode_storage_value(value: Any) -> str:
    if value is None:
        return "null"

    if isinstance(value, SecretStr):
        return value.get_secret_value()

    if isinstance(value, Enum):
        return str(value.value)

    if isinstance(value, UUID):
        return value.hex

    if isinstance(value, bool):
        return str(int(value))

    if isinstance(value, (list, tuple)):
        return ",".join(sorted(map(encode_storage_value, value)))

    return str(value)
