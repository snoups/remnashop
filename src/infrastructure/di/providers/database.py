from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide
from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.application.common.uow import UnitOfWork
from src.core.config import AppConfig
from src.infrastructure.database import UnitOfWorkImpl


class DatabaseProvider(Provider):
    scope = Scope.APP

    uow = provide(source=UnitOfWorkImpl, provides=UnitOfWork, scope=Scope.REQUEST)

    @provide
    async def get_engine(self, config: AppConfig) -> AsyncIterable[AsyncEngine]:
        logger.debug("Creating AsyncEngine")
        engine = create_async_engine(
            url=config.database.dsn,
            echo=config.database.echo,
            echo_pool=config.database.echo_pool,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_timeout=config.database.pool_timeout,
            pool_recycle=config.database.pool_recycle,
            pool_pre_ping=True,
            pool_reset_on_return="rollback",
            query_cache_size=500,
            connect_args={
                "server_settings": {
                    "jit": "on",
                    "statement_timeout": "60000",
                    "idle_in_transaction_session_timeout": "300000",
                },
                "command_timeout": 30,
                "timeout": 10,
            },
        )
        yield engine
        logger.debug("Disposing AsyncEngine")
        await engine.dispose()

    @provide
    def get_session_maker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        logger.debug("Created session maker")
        return session_maker

    @provide(scope=Scope.REQUEST)
    async def provide_session(
        self,
        pool: async_sessionmaker[AsyncSession],
    ) -> AsyncIterable[AsyncSession]:
        async with pool() as session:
            yield session
