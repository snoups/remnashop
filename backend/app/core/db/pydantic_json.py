from typing import Any, Optional, TypeVar

from pydantic import BaseModel
from sqlalchemy import Dialect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

from app.core.db import json_helpers as json

_T = TypeVar("_T", bound=BaseModel)


class PydanticJSON(TypeDecorator[_T]):
    """Maps a JSONB column straight to a Pydantic model instead of `dict[str, Any]` -
    callers get the model as-is, no manual dump/validate in the DAO."""

    impl = JSONB
    cache_ok = True

    def __init__(self, model: type[_T]) -> None:
        super().__init__()
        self._model = model

    def process_bind_param(self, value: Optional[_T], dialect: Dialect) -> Optional[Any]:
        if value is None:
            return None
        return json.dump_json_safe(value, self._model)

    def process_result_value(self, value: Optional[Any], dialect: Dialect) -> Optional[_T]:
        if value is None:
            return None
        return self._model.model_validate(value)
