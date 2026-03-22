from uuid import UUID

from adaptix import Retort
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from remnapy.exceptions import BadRequestError
from remnapy.models import CreateUserRequestDto, UserResponseDto

from src.application.common.dao import SubscriptionDao, UserDao
from src.application.dto.user import UserDto
from src.application.use_cases.importer.dto import ExportedUserDto
from src.application.use_cases.remnawave.commands.synchronization import (
    SyncRemnaUser,
    SyncRemnaUserDto,
)
from src.infrastructure.redis.keys import SyncRunningKey
from src.infrastructure.taskiq.broker import broker


@broker.task
@inject(patch_module=True)
async def import_exported_users_task(
    imported_users: list[ExportedUserDto],
    active_internal_squads: list[UUID],
    remnawave_sdk: FromDishka[RemnawaveSDK],
) -> tuple[int, int]:
    logger.info(f"Starting import of '{len(imported_users)}' users")

    success_count = 0
    failed_count = 0

    for user in imported_users:
        try:
            created_user = CreateUserRequestDto.model_validate(user)
            created_user.active_internal_squads = active_internal_squads
            await remnawave_sdk.users.create_user(created_user)
            success_count += 1
        except BadRequestError as error:
            logger.warning(f"User '{user.username}' already exists, skipping. Error: {error}")
            failed_count += 1

        except Exception as exception:
            logger.exception(f"Failed to create user '{user.username}' exception: {exception}")
            failed_count += 1

    logger.info(f"Import completed: '{success_count}' successful, '{failed_count}' failed")
    return success_count, failed_count


@broker.task
@inject(patch_module=True)
async def sync_all_users_from_panel_task(  # noqa: C901
    retort: FromDishka[Retort],
    redis: FromDishka[Redis],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    user_dao: FromDishka[UserDao],
    subscription_dao: FromDishka[SubscriptionDao],
    sync_remna_user: FromDishka[SyncRemnaUser],
) -> dict[str, int]:
    key = retort.dump(SyncRunningKey())
    all_remna_users: list[UserResponseDto] = []
    limit = 50
    offset = 0

    while True:
        response = await remnawave_sdk.users.get_all_users(start=offset, size=limit)
        if not response.users:
            break
        all_remna_users.extend(response.users)
        if len(response.users) < limit:
            break
        offset += len(response.users)

    bot_users: list[UserDto] = []
    limit = 500
    offset = 0

    while True:
        batch = await user_dao.get_all(limit=limit, offset=offset)
        if not batch:
            break
        bot_users.extend(batch)
        if len(batch) < limit:
            break
        offset += len(batch)

    bot_users_map = {user.telegram_id: user for user in bot_users}

    logger.info(f"Total users in panel: '{len(all_remna_users)}'")
    logger.info(f"Total users in bot: '{len(bot_users)}'")

    added_users = 0
    added_subscription = 0
    updated = 0
    errors = 0
    missing_telegram = 0

    try:
        for remna_user in all_remna_users:
            try:
                if not remna_user.telegram_id:
                    missing_telegram += 1
                    continue

                user = bot_users_map.get(remna_user.telegram_id)

                if not user:
                    await sync_remna_user.system(SyncRemnaUserDto(remna_user, True))
                    added_users += 1
                else:
                    current_subscription = await subscription_dao.get_current(user.telegram_id)
                    if not current_subscription:
                        await sync_remna_user.system(SyncRemnaUserDto(remna_user, True))
                        added_subscription += 1
                    else:
                        changed = await sync_remna_user.system(SyncRemnaUserDto(remna_user, True))
                        if changed:
                            updated += 1

            except Exception as exception:
                logger.exception(
                    f"Error syncing RemnaUser '{remna_user.telegram_id}' exception: {exception}"
                )
                errors += 1

        result = {
            "total_panel_users": len(all_remna_users),
            "total_bot_users": len(bot_users),
            "added_users": added_users,
            "added_subscription": added_subscription,
            "updated": updated,
            "errors": errors,
            "missing_telegram": missing_telegram,
        }

        logger.info(f"Sync users summary: '{result}'")
        return result
    finally:
        await redis.delete(key)
