#!/bin/sh
set -e

ASSETS_CONTAINER_PATH="/opt/remnashop/assets"
ASSETS_DEFAULT_PATH="/opt/remnashop/assets.default"
ASSETS_BACKUP_PATH="${ASSETS_CONTAINER_PATH}/.bak"

RESET_FLAG="${RESET_ASSETS:-false}"
IS_VOLUME_EMPTY=$(ls -A $ASSETS_CONTAINER_PATH 2>/dev/null)

UVICORN_RELOAD_ARGS=""


echo "Starting asset initialization, reset flag is '${RESET_FLAG}'"

if [ "$RESET_FLAG" = 'true' ]; then
    echo "Reset assets flag is set to true, archiving existing data and setting default"

    if [ -n "$IS_VOLUME_EMPTY" ]; then
        echo "Found existing assets, creating backup"

        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILENAME="assets_backup_${TIMESTAMP}.tar.gz"

        mkdir -p $ASSETS_BACKUP_PATH
        tar --exclude='.bak' -czf "$ASSETS_BACKUP_PATH/$BACKUP_FILENAME" -C "$ASSETS_CONTAINER_PATH" .
        
        if [ $? -eq 0 ]; then
            echo "Successfully created archive at '${ASSETS_BACKUP_PATH}/${BACKUP_FILENAME}'"
        else
            echo "Error creating backup archive, continuing with caution"
        fi

        echo "Removing existing assets from '${ASSETS_CONTAINER_PATH}'"
        find $ASSETS_CONTAINER_PATH -mindepth 1 -maxdepth 1 ! -name ".bak" -exec rm -rf {} +
    else
        echo "Assets volume is empty, no need to archive"
    fi

    echo "Copying all default assets for full reset"
    cp -a "$ASSETS_DEFAULT_PATH/." "$ASSETS_CONTAINER_PATH"
    echo "Assets reset complete"

elif [ -z "$IS_VOLUME_EMPTY" ]; then
    echo "Volume mounted to '${ASSETS_CONTAINER_PATH}' is empty, copying default assets for initial setup"
    cp -a "$ASSETS_DEFAULT_PATH/." "$ASSETS_CONTAINER_PATH"
    echo "Default assets successfully copied"

else
    echo "Volume mounted to '${ASSETS_CONTAINER_PATH}' is not empty, skipping asset initialization to preserve user data"
fi


echo "Migrating database"

if ! alembic -c src/infrastructure/database/alembic.ini upgrade head; then
    echo "Database migration failed! Exiting container..."
    exit 1
fi

echo "Migrations deployed successfully"


if [ "$UVICORN_RELOAD_ENABLED" = "true" ]; then
    echo "Uvicorn will run with reload enabled"
    UVICORN_RELOAD_ARGS="--reload --reload-dir /opt/remnashop/src --reload-dir /opt/remnashop/assets --reload-include *.ftl"
else
    echo "Uvicorn will run without reload"
fi

exec uvicorn src.__main__:application --host "${APP_HOST}" --port "${APP_PORT}" --factory --use-colors ${UVICORN_RELOAD_ARGS}