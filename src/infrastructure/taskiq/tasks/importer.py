from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from remnawave import RemnawaveSDK
from remnawave.exceptions import BadRequestError
from remnawave.models import CreateUserRequestDto, UserResponseDto, UsersResponseDto

from src.core.constants import IMPORTED_TAG
from src.core.utils.formatters import format_limits_to_plan_type
from src.core.utils.types import RemnaUserDto
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
)
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.tasks.subscriptions import sync_current_subscription_task
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.user import UserService


@broker.task
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


@broker.task
@inject
async def sync_imported_user_task(remna_user: RemnaUserDto) -> None:
    if not remna_user.telegram_id:
        logger.warning(
            f"Skipping sync for RemnaUser '{remna_user.username}', missing 'telegram_id'"
        )
        return

    logger.info(f"Starting sync for imported user '{remna_user.telegram_id}'")

    if remna_user.tag != IMPORTED_TAG:
        logger.debug(f"User '{remna_user.telegram_id}' is not tagged as '{IMPORTED_TAG}', skipping")
        return

    await create_user_from_panel_task.kiq(remna_user)


@broker.task
@inject
async def sync_all_users_from_panel_task(
    remnawave: FromDishka[RemnawaveSDK],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> dict[str, int]:
    all_remna_users: list[UserResponseDto] = []
    start = 0
    size = 50

    while True:
        response = await remnawave.users.get_all_users_v2(start=start, size=size)
        logger.success(response)
        if not isinstance(response, UsersResponseDto) or not response.users:
            break

        all_remna_users.extend(response.users)
        start += len(response.users)

        if len(response.users) < size:
            break

    bot_users = await user_service.get_all()
    bot_users_map = {user.telegram_id: user for user in bot_users}

    logger.info(f"Total users in panel: '{len(all_remna_users)}'")
    logger.info(f"Total users in bot: '{len(bot_users)}'")

    added = 0
    updated = 0
    errors = 0
    missing_telegram = 0

    for remna_user in all_remna_users:
        try:
            if not remna_user.telegram_id:
                missing_telegram += 1
                continue

            user = bot_users_map.get(remna_user.telegram_id)

            if not user:
                await create_user_from_panel_task.kiq(remna_user)
                added += 1
            else:
                current_subscription = await subscription_service.get_current(user.telegram_id)
                if not current_subscription:
                    await create_user_from_panel_task.kiq(remna_user)
                    added += 1
                else:
                    logger.success(remna_user.hwid_device_limit)
                    remna_subscription = RemnaSubscriptionDto.from_remna_user(
                        remna_user.model_dump()
                    )
                    logger.success(remna_subscription.device_limit)
                    await sync_current_subscription_task.kiq(
                        remna_user.telegram_id, remna_subscription
                    )
                    updated += 1

        except Exception as exception:
            logger.exception(
                f"Error syncing RemnaUser '{remna_user.telegram_id}' exception: {exception}"
            )
            errors += 1

    result = {
        "total_panel_users": len(all_remna_users),
        "total_bot_users": len(bot_users),
        "added": added,
        "updated": updated,
        "errors": errors,
        "missing_telegram": missing_telegram,
    }

    logger.info(f"Sync users summary: '{result}'")
    return result


@broker.task
@inject
async def create_user_from_panel_task(
    remna_user: RemnaUserDto,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    if not remna_user.telegram_id:
        logger.warning(f"Skipping user creation for '{remna_user.username}', missing 'telegram_id'")
        return

    user = await user_service.get(telegram_id=remna_user.telegram_id)

    if not user:
        logger.debug(f"User '{remna_user.telegram_id}' not found in bot, creating new user")
        user = await user_service.create_from_panel(remna_user)

    remna_subscription = RemnaSubscriptionDto.from_remna_user(remna_user.model_dump())

    if not remna_subscription.url:
        subscription_url = await remnawave_service.get_subscription_url(remna_user.uuid)
        remna_subscription.url = subscription_url  # type: ignore[assignment]

    temp_plan = PlanSnapshotDto(
        id=-1,
        name=IMPORTED_TAG,
        type=format_limits_to_plan_type(
            remna_subscription.traffic_limit,
            remna_subscription.device_limit,
        ),
        traffic_limit=remna_subscription.traffic_limit,
        device_limit=remna_subscription.device_limit,
        duration=-1,
        internal_squads=remna_subscription.internal_squads,
    )
    subscription = SubscriptionDto(
        user_remna_id=remna_user.uuid,
        status=remna_user.status,
        traffic_limit=temp_plan.traffic_limit,
        device_limit=temp_plan.device_limit,
        internal_squads=remna_subscription.internal_squads,
        expire_at=remna_user.expire_at,
        url=remna_subscription.url,
        plan=temp_plan,
    )
    await subscription_service.create(user, subscription)
    logger.info(f"User and subscription successfully created for '{remna_user.telegram_id}'")
