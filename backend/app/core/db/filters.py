from collections.abc import Collection

from sqlalchemy import ARRAY, BigInteger, ColumnElement, any_, literal
from sqlalchemy.orm import InstrumentedAttribute


def in_ids(column: InstrumentedAttribute[int], ids: Collection[int]) -> ColumnElement[bool]:
    # one array bind, not IN (...): a long id list would pass asyncpg's
    # 32,767 bind-parameter cap
    return column == any_(literal(list(ids), ARRAY(BigInteger)))
