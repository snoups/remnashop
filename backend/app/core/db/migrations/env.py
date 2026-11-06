import asyncio
from logging.config import fileConfig
from typing import Optional

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import AppConfig
from app.core.db import models  # noqa: F401 (registers models on BaseSql.metadata)
from app.core.db.base import BaseSql

config = context.config
app_config = AppConfig.get()
db_config = app_config.database

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BaseSql.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(url=db_config.dsn)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


external_connection: Optional[Connection] = config.attributes.get("connection")

if context.is_offline_mode():
    run_migrations_offline()
elif external_connection is not None:
    # the caller's open transaction stays uncommitted
    do_run_migrations(external_connection)
else:
    asyncio.run(run_migrations_online())
