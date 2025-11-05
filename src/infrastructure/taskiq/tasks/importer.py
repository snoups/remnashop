from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from remnawave import RemnawaveSDK
from remnawave.exceptions import BadRequestError
from remnawave.models import CreateUserRequestDto, UserResponseDto, UsersResponseDto
from remnawave.models.webhook import UserDto as RemnaUserDto

from src.core.utils.formatters import (
    format_bytes_to_gb,
    format_device_count,
    format_limits_to_plan_type,
)
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    SubscriptionDto,
)
from src.infrastructure.taskiq.broker import broker
from src.services.importer import BOTS, ImporterService
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.user import UserService


@broker.task
@inject
async def import_exported_users_task(
    imported_users: list,
    remnawave: FromDishka[RemnawaveSDK],
    active_internal_squads: list[UUID] = [],
) -> tuple[int, int]:
    logger.info(f"[TASK] Starting import of '{len(imported_users)}' users")

    success_count = 0
    failed_count = 0

    for user in imported_users:
        try:
            if not active_internal_squads:
                await remnawave.users.create_user(CreateUserRequestDto.model_validate(user))
            else:
                await remnawave.users.create_user(
                    CreateUserRequestDto(**user, active_internal_squads=active_internal_squads)
                    # CreateUserRequestDto(
                    #     username=user["username"],
                    #     status=user["status"],
                    #     telegram_id=user["telegram_id"],
                    #     active_internal_squads=active_internal_squads,
                    #     expire_at=user["expire_at"],
                    #     traffic_limit_bytes=user["traffic_limit_bytes"],
                    #     hwid_device_limit=user["hwid_device_limit"],
                    #     tag=user["tag"],
                    # )
                )
            success_count += 1
        except BadRequestError as error:
            logger.warning(
                f"[TASK] User '{user['username']}' already exists, skipping. Error: {error}"
            )
            failed_count += 1

        except Exception as exception:
            logger.exception(f"[TASK] Failed to create user '{user['username']}': {exception}")
            failed_count += 1

    logger.info(f"[TASK] Import completed: '{success_count}' successful, '{failed_count}' failed")
    return success_count, failed_count


@broker.task
@inject
async def sync_imported_user_task(
    remna_user: RemnaUserDto,
    remnawave_service: FromDishka[RemnawaveService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    if not remna_user.telegram_id:
        logger.warning(f"[TASK] Skipping sync for user '{remna_user.uuid}': missing telegram_id")
        return

    logger.info(f"[TASK] Starting sync for imported user '{remna_user.telegram_id}'")

    if remna_user.tag != "IMPORTED":
        logger.debug(f"[TASK] User '{remna_user.telegram_id}' is not tagged as IMPORTED, skipping")
        return

    user = await user_service.get(remna_user.telegram_id)

    if not user:
        logger.info(f"[TASK] User '{remna_user.telegram_id}' not found — creating new user")
        user = await user_service.create_from_panel(remna_user)

    subscription_url = await remnawave_service.get_subscription_url(user)

    if not subscription_url:
        logger.warning(f"[TASK] User '{remna_user.telegram_id}' has no subscription URL, skipping")
        return

    traffic_limit = format_bytes_to_gb(remna_user.traffic_limit_bytes)
    device_limit = format_device_count(remna_user.hwid_device_limit)

    temp_plan = PlanSnapshotDto(
        id=-1,
        name="IMPORTED",
        type=format_limits_to_plan_type(traffic_limit, device_limit),
        traffic_limit=traffic_limit,
        device_limit=device_limit,
        duration=-1,
        internal_squads=[squad.uuid for squad in remna_user.active_internal_squads],
    )

    new_subscription = SubscriptionDto(
        user_remna_id=remna_user.uuid,
        status=remna_user.status,
        traffic_limit=temp_plan.traffic_limit,
        device_limit=temp_plan.device_limit,
        internal_squads=temp_plan.internal_squads,
        expire_at=remna_user.expire_at,
        url=subscription_url,
        plan=temp_plan,
    )
    await subscription_service.create(user, new_subscription)


@broker.task
@inject
async def get_users_by_bot_task(
    bot_name: str,
    remnawave: FromDishka[RemnawaveSDK],
    importer_service: FromDishka[ImporterService],
) -> list:
    if bot_name not in BOTS:
        logger.warning(f"Bot '{bot_name}' not configured in BOTS dict")
        return []

    pattern = BOTS[bot_name]
    users: list[UserResponseDto] = []
    start = 0
    size = 25

    while True:
        response = await remnawave.users.get_all_users_v2(start=start, size=size)

        if not isinstance(response, UsersResponseDto):
            break

        if not response.users:
            break

        matched_users = [user for user in response.users if pattern.match(user.username)]
        users.extend(matched_users)

        start += len(response.users)

        if len(response.users) < size:
            break

    logger.info(f"Found {len(users)} users for bot '{bot_name}'")
    return users
