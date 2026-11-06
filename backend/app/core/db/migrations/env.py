import asyncio
from logging.config import fileConfig
from typing import Final, Iterable, Optional, Union

from alembic import context
from alembic.operations import MigrationScript
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
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

# 0001-0046 belong to the old app's chain (app/cli/legacy/migrations)
_FIRST_REVISION: Final[int] = 1000


def process_revision_directives(
    context: MigrationContext,
    revision: Union[str, Iterable[Optional[str]], Iterable[str]],
    directives: list[MigrationScript],
) -> None:
    head = ScriptDirectory.from_config(config).get_current_head()
    next_revision = _FIRST_REVISION if head is None else int(head) + 1
    directives[0].rev_id = f"{next_revision:04}"


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
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
        process_revision_directives=process_revision_directives,
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
