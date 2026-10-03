from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork


class DatabaseProvider(Provider):
    scope = Scope.APP

    uow = provide(UnitOfWork, scope=Scope.REQUEST)

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
                    "statement_timeout": str(config.database.statement_timeout_ms),
                    "idle_in_transaction_session_timeout": str(
                        config.database.idle_in_transaction_timeout_ms
                    ),
                },
                "command_timeout": config.database.command_timeout_s,
                "timeout": config.database.connect_timeout_s,
            },
        )

        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except OperationalError:
            raise
        except Exception as exc:
            logger.exception(f"Failed to connect to Postgres: {exc}")
            raise OperationalError(None, None, exc) from exc
        logger.debug("Connected to Postgres")

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
