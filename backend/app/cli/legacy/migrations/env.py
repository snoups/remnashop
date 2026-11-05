from alembic import context

from app.core.config import AppConfig

# enum values added by one revision are used by the next, so each commits on its own
# owner_id is None: 0019 then leaves roles alone; the migration assigns them itself
context.configure(
    connection=context.config.attributes["connection"],
    target_metadata=None,
    crypt_key=AppConfig.get().crypt_key.get_secret_value(),
    owner_id=None,
    transaction_per_migration=True,
)

with context.begin_transaction():
    context.run_migrations()
