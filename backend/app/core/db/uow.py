from types import TracebackType
from typing import Optional, Self, Type

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> Self:
        logger.debug("SQL transaction started")
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        # Session lifecycle belongs to the DI provider; UoW only owns the transaction.
        # Auto-commit on a clean exit -- a forgotten `await uow.commit()` used to be a
        # silent no-op (flush-only writes invisible outside the transaction, see
        # docs/architecture/usecases.md). Explicit commit() is now redundant but
        # harmless; explicit rollback() is still meaningful for an early-abort path.
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self.session.commit()
        logger.debug("SQL transaction committed")

    async def rollback(self) -> None:
        await self.session.rollback()
        logger.warning("SQL transaction rolled back")
