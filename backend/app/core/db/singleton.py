from typing import Any, TypeVar

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import BaseSql

_Row = TypeVar("_Row", bound=BaseSql)


async def get_or_create_singleton(
    session: AsyncSession, model: type[_Row], row_id: int, **values: Any
) -> _Row:
    """Fetch the always-id=N row of a settings-style table, creating it if absent.

    ON CONFLICT DO NOTHING rather than session.add: on a fresh database the
    first few requests arrive in parallel and would otherwise each insert the
    same row, and all but one blow up on the primary key.
    """
    row = await session.get(model, row_id)
    if row is not None:
        return row

    await session.execute(pg_insert(model).values(id=row_id, **values).on_conflict_do_nothing())
    return await session.get_one(model, row_id)
