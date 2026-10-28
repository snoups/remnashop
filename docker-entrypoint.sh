#!/bin/sh
set -e

TARGET="$1"

if [ "$TARGET" = "api" ]; then
    if ! python -m app.cli.pre_migration_dump; then
        echo "Pre-migration backup failed, migrations not applied! Exiting container..."
        exit 1
    fi
    echo "Running database migrations"
    if ! alembic -c alembic.ini upgrade head; then
        echo "Database migration failed! Exiting container..."
        exit 1
    fi
    echo "Migrations applied"
fi

case "$TARGET" in
    api)
        UVICORN_RELOAD_ARGS=""
        if [ "$UVICORN_RELOAD_ENABLED" = "true" ]; then
            echo "Uvicorn will run with reload enabled"
            UVICORN_RELOAD_ARGS="--reload --reload-dir /opt/remnashop/app"
        else
            echo "Uvicorn will run without reload"
        fi
        exec uvicorn app.api.__main__:create_app --factory --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-5000}" --use-colors $UVICORN_RELOAD_ARGS
        ;;
    telegram)
        exec python -m app.telegram
        ;;
    worker)
        # A new tasks.py isn't picked up until it's listed here;
        # tests/worker/test_container.py checks every one is.
        # -w 1: WORKER_STARTUP binds a single metrics HTTP server port and
        # starts a single worker-gauges poller (see app/worker/lifespan.py) --
        # a second child process would collide on the port and double-sample
        # the gauges.
        exec taskiq worker -w 1 --max-async-tasks "${WORKER_MAX_ASYNC_TASKS:-25}" app.core.broker:broker app.worker.lifespan app.modules.event_log.tasks app.modules.subscriptions.tasks app.modules.transactions.tasks app.modules.auth.tasks app.modules.referrals.tasks app.modules.backups.tasks app.modules.blacklist.tasks app.modules.users.tasks app.modules.advertising.tasks app.modules.overview.tasks app.modules.announcements.tasks app.modules.loyalty.tasks app.modules.notifications.tasks app.modules.broadcasts.tasks app.modules.email.tasks app.modules.customer_notifications.tasks app.modules.promocodes.tasks
        ;;
    scheduler)
        # Only includes modules with a schedule-labeled task -- not a full
        # mirror of worker's module list, since taskiq scheduler only reads
        # schedule labels off these modules, it never executes their tasks.
        # It also dispatches every delayed task retry via retry_schedule_source,
        # so it's an operational dependency for retry timing: a scheduler outage
        # stalls (does not lose -- ListRedisScheduleSource recovers past
        # buckets) all pending retries.
        exec taskiq scheduler app.worker.scheduler:scheduler app.modules.event_log.tasks app.modules.subscriptions.tasks app.modules.transactions.tasks app.modules.auth.tasks app.modules.backups.tasks app.modules.blacklist.tasks app.modules.users.tasks app.modules.overview.tasks app.modules.announcements.tasks app.modules.loyalty.tasks app.modules.notifications.tasks app.modules.broadcasts.tasks app.modules.promocodes.tasks
        ;;
    cli)
        exec python -m app.cli
        ;;
    *)
        echo "Usage: docker-entrypoint.sh {api|telegram|worker|scheduler|cli}" >&2
        exit 1
        ;;
esac
