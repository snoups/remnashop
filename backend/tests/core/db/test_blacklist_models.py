import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import Blacklist, BlacklistSource


async def test_blacklist_singleton_defaults(session: AsyncSession) -> None:
    session.add(Blacklist(id=1))
    await session.flush()
    row = (await session.execute(select(Blacklist))).scalar_one()
    assert row.blocked_telegram_ids == []
    assert row.blocked_emails == []


async def test_blacklist_source_url_unique(session: AsyncSession) -> None:
    session.add(BlacklistSource(url="https://a.example/list.txt"))
    await session.flush()
    session.add(BlacklistSource(url="https://a.example/list.txt"))
    with pytest.raises(Exception):
        await session.flush()
