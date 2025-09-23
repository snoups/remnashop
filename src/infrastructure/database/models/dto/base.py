from typing import Any, Iterable, Optional, Type, TypeVar

from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict, PrivateAttr

from src.infrastructure.database.models.sql import BaseSql

SqlModel = TypeVar("SqlModel", bound=BaseSql)
DtoModel = TypeVar("DtoModel", bound="BaseDto")


class BaseDto(_BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        from_attributes=True,
        populate_by_name=True,
    )

    @classmethod
    def from_model(cls: Type[DtoModel], model_instance: Optional[SqlModel]) -> Optional[DtoModel]:
        if model_instance is None:
            return None
        return cls.model_validate(model_instance)

    @classmethod
    def from_model_list(cls: Type[DtoModel], model_instances: Iterable[SqlModel]) -> list[DtoModel]:
        dtos = [cls.from_model(instance) for instance in model_instances]
        return [dto for dto in dtos if dto is not None]


class TrackableDto(BaseDto):
    __changed_data: dict[str, Any] = PrivateAttr(default_factory=dict)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        self.__changed_data[name] = value

    @property
    def changed_data(self) -> dict[str, Any]:
        return self.__changed_data
