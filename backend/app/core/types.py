from typing import TYPE_CHECKING, Annotated, NewType, TypeAlias

from pydantic import PlainValidator

if TYPE_CHECKING:
    ListStr: TypeAlias = list[str]
else:
    ListStr = NewType("ListStr", list[str])

StringList: TypeAlias = Annotated[
    ListStr, PlainValidator(lambda x: [s.strip() for s in x.split(",")])
]
