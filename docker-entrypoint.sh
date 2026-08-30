#!/bin/sh
set -e

TARGET="$1"

if [ "$TARGET" = "api" ]; then
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
        # Each task module listed here needs its providers registered in
        # backend/app/worker/container.py's create_worker_container() too --
        # the two lists are kept in sync by hand, see that file's comment.
        exec taskiq worker app.worker.broker:broker app.worker.lifespan app.modules.event_log.tasks app.modules.translations.tasks app.modules.subscriptions.tasks
        ;;
    scheduler)
        # Only includes modules with a schedule-labeled task -- not a full
        # mirror of worker's module list, since taskiq scheduler only reads
        # schedule labels off these modules, it never executes their tasks.
        exec taskiq scheduler app.worker.scheduler:scheduler app.modules.subscriptions.tasks
        ;;
    *)
        echo "Usage: docker-entrypoint.sh {api|telegram|worker|scheduler}" >&2
        exit 1
        ;;
esac
