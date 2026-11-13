from importlib import import_module

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

_MIGRATION = import_module("app.core.db.migrations.versions.1007_recurring_retry_policy")


@pytest.fixture
async def legacy_consent_schema(session, monkeypatch):
    # Temporary tables shadow the application schema on this connection only;
    # the real migration can exercise rollback data without changing its revision.
    statements = (
        "CREATE TEMP TABLE users (id integer PRIMARY KEY)",
        "CREATE TEMP TABLE subscriptions (id integer PRIMARY KEY, user_id integer NOT NULL "
        "REFERENCES users(id))",
        "CREATE TEMP TABLE recurring_consents (id integer PRIMARY KEY, "
        "user_id integer REFERENCES users(id) ON DELETE SET NULL, "
        "owner_user_id integer REFERENCES users(id) ON DELETE CASCADE, "
        "subscription_id integer REFERENCES subscriptions(id))",
        "CREATE TEMP TABLE transactions (id integer PRIMARY KEY, user_id integer NOT NULL "
        "REFERENCES users(id), recurring_consent_id integer REFERENCES recurring_consents(id))",
        "CREATE TEMP TABLE recurring_payments (subscription_id integer PRIMARY KEY "
        "REFERENCES subscriptions(id), consent_id integer REFERENCES recurring_consents(id))",
        "INSERT INTO users VALUES (1), (2)",
        "INSERT INTO subscriptions VALUES (10, 2)",
    )
    for statement in statements:
        await session.execute(text(statement))
    monkeypatch.setattr(_MIGRATION.context, "is_offline_mode", lambda: False)
    return session


def _upgrade_owner(session) -> None:
    # Obtain the connection through the session after its nested transaction has
    # started, so SQLAlchemy owns the SAVEPOINT and can recover from rejected DDL.
    with Operations.context(MigrationContext.configure(session.connection())):
        _MIGRATION._upgrade_legacy_consent_owner()


async def test_reupgrade_removes_only_purged_unreferenced_authorization(
    legacy_consent_schema, session
) -> None:
    await session.execute(
        text(
            "INSERT INTO recurring_consents (id, user_id, owner_user_id, subscription_id) VALUES "
            "(1, 1, NULL, NULL), (2, 2, NULL, NULL), (3, NULL, NULL, 10), "
            "(4, NULL, NULL, NULL), (5, NULL, 2, NULL)"
        )
    )
    await session.execute(text("INSERT INTO transactions VALUES (100, 2, 4)"))
    await session.execute(text("DELETE FROM users WHERE id = 1"))

    await legacy_consent_schema.run_sync(_upgrade_owner)

    assert (
        await session.execute(text("SELECT id, owner_user_id FROM recurring_consents ORDER BY id"))
    ).all() == [(2, 2), (3, 2), (4, 2), (5, 2)]
    with pytest.raises(IntegrityError):
        async with legacy_consent_schema.begin_nested():
            await legacy_consent_schema.execute(
                text("INSERT INTO recurring_consents (id) VALUES (6)")
            )


async def test_reupgrade_keeps_unresolved_referenced_authorization_and_fails_closed(
    legacy_consent_schema, session
) -> None:
    await session.execute(text("INSERT INTO recurring_consents (id) VALUES (1)"))
    await session.execute(text("INSERT INTO recurring_payments VALUES (10, 1)"))

    with pytest.raises(IntegrityError) as error:
        async with legacy_consent_schema.begin_nested():
            await legacy_consent_schema.run_sync(_upgrade_owner)

    assert error.value.orig.sqlstate == "23502"
    assert await session.scalar(text("SELECT count(*) FROM recurring_consents WHERE id = 1")) == 1
    assert await session.scalar(text("SELECT consent_id FROM recurring_payments")) == 1
