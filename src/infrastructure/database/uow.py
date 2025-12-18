from types import TracebackType
from typing import Optional, Self, Type

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .repositories import RepositoriesFacade


class UnitOfWork:
    session_pool: async_sessionmaker[AsyncSession]
    session: Optional[AsyncSession] = None

    repository: RepositoriesFacade

    def __init__(self, session_pool: async_sessionmaker[AsyncSession]) -> None:
        self.session_pool = session_pool

    async def __aenter__(self) -> Self:
        self.session = self.session_pool()
        self.repository = RepositoriesFacade(session=self.session)
        logger.debug(f"Opened session '{id(self.session)}'")
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.session is None:
            return

        session_id = id(self.session)
        try:
            if exc_type is None:
                await self.commit()
            else:
                logger.warning(
                    f"Exception detected '{exc_val}', rolling back session '{session_id}'"
                )
                await self.rollback()
        finally:
            await self.session.close()
            logger.debug(f"Closed session '{session_id}'")
            self.session = None

    async def commit(self) -> None:
        if self.session:
            await self.session.commit()
            logger.debug(f"Session '{id(self.session)}' committed")

    async def rollback(self) -> None:
        if self.session:
            await self.session.rollback()
            logger.debug(f"Session '{id(self.session)}' rolled back")
