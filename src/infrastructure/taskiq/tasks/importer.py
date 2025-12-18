from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import BadRequestError
from remnapy.models import CreateUserRequestDto, UserResponseDto

from src.core.storage.keys import SyncRunningKey
from src.infrastructure.redis.repository import RedisRepository
from src.infrastructure.taskiq.broker import broker
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.user import UserService


@broker.task(retry_on_error=False)
@inject
async def import_exported_users_task(
    imported_users: list[dict],
    active_internal_squads: list[UUID],
    remnawave: FromDishka[RemnawaveSDK],
) -> tuple[int, int]:
    logger.info(f"Starting import of '{len(imported_users)}' users")

    success_count = 0
    failed_count = 0

    for user in imported_users:
        try:
            username = user["username"]
            created_user = CreateUserRequestDto.model_validate(user)
            created_user.active_internal_squads = active_internal_squads
            await remnawave.users.create_user(created_user)
            success_count += 1
        except BadRequestError as error:
            logger.warning(f"User '{username}' already exists, skipping. Error: {error}")
            failed_count += 1

        except Exception as exception:
            logger.exception(f"Failed to create user '{username}' exception: {exception}")
            failed_count += 1

    logger.info(f"Import completed: '{success_count}' successful, '{failed_count}' failed")
    return success_count, failed_count


@broker.task(retry_on_error=False)
@inject
async def sync_all_users_from_panel_task(
    redis_repository: FromDishka[RedisRepository],
    remnawave: FromDishka[RemnawaveSDK],
    remnawave_service: FromDishka[RemnawaveService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> dict[str, int]:
    key = SyncRunningKey()
    all_remna_users: list[UserResponseDto] = []
    start = 0
    size = 50

    stats = await remnawave.system.get_stats()
    total_users = stats.users.total_users

    for start in range(0, total_users, size):
        response = await remnawave.users.get_all_users(start=start, size=size)
        if not response.users:
            break

        all_remna_users.extend(response.users)
        start += len(response.users)

        if len(response.users) < size:
            break

    bot_users = await user_service.get_all()
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
                    await remnawave_service.sync_user(remna_user)
                    added_users += 1
                else:
                    current_subscription = await subscription_service.get_current(user.telegram_id)
                    if not current_subscription:
                        await remnawave_service.sync_user(remna_user)
                        added_subscription += 1
                    else:
                        await remnawave_service.sync_user(remna_user)
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
        await redis_repository.delete(key)
