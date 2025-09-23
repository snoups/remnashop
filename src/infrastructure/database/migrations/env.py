import asyncio
from logging.config import fileConfig
from typing import Iterable, Optional, Union

from alembic import context
from alembic.operations import MigrationScript
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.core.config import AppConfig
from src.infrastructure.database.models.sql import BaseSql

config = context.config
db_config = AppConfig.get().database

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BaseSql.metadata


def process_revision_directives(
    context: MigrationContext,
    revision: Union[str, Iterable[Optional[str]], Iterable[str]],
    directives: list[MigrationScript],
) -> None:
    migration_script = directives[0]

    script_directory = ScriptDirectory.from_config(config)
    head_revision = script_directory.get_current_head()

    if head_revision is None:
        new_rev_id = 1
    else:
        last_rev_id = int(head_revision.lstrip("0"))
        new_rev_id = last_rev_id + 1

    migration_script.rev_id = f"{new_rev_id:04}"


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(url=db_config.dsn)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
