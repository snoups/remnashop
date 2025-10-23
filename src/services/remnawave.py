from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from remnawave import RemnawaveSDK
from remnawave.models import (
    CreateUserRequestDto,
    DeleteUserResponseDto,
    UpdateUserRequestDto,
    UserResponseDto,
)
from remnawave.models.webhook import (
    HwidUserDeviceDto as RemnaHwidUserDeviceDto,
)
from remnawave.models.webhook import NodeDto as RemnaNodeDto
from remnawave.models.webhook import UserDto as RemnaUserDto
from remnawave.models.webhook import UserHwidDeviceEventDto

from src.core.config import AppConfig
from src.core.constants import DATETIME_FORMAT, REMNASHOP_PREFIX
from src.core.enums import (
    RemnaNodeEvent,
    RemnaUserEvent,
    RemnaUserHwidDevicesEvent,
    SubscriptionStatus,
    SystemNotificationType,
    UserNotificationType,
)
from src.core.utils.formatters import (
    format_country_code,
    format_days_to_datetime,
    format_device_count,
    format_gb_to_bytes,
    i18n_format_bytes_to_unit,
    i18n_format_limit,
)
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import PlanSnapshotDto, UserDto
from src.infrastructure.redis import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import (
    send_subscription_expire_notification_task,
    send_subscription_limited_notification_task,
    send_system_notification_task,
)

from .base import BaseService


class RemnawaveService(BaseService):
    remnawave: RemnawaveSDK

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        remnawave: RemnawaveSDK,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.remnawave = remnawave

    async def create_user(self, user: UserDto, plan: PlanSnapshotDto) -> UserResponseDto:
        logger.info(f"{log(user)} Creating Remnawave user for plan '{plan.name}'")

        created_user = await self.remnawave.users.create_user(
            CreateUserRequestDto(
                expire_at=format_days_to_datetime(plan.duration),
                username=user.remna_name,
                traffic_limit_bytes=format_gb_to_bytes(plan.traffic_limit),
                # traffic_limit_strategy=,
                description=user.remna_description,
                # tag=,
                telegram_id=user.telegram_id,
                hwidDeviceLimit=format_device_count(plan.device_limit),
                active_internal_squads=[str(uid) for uid in plan.squad_ids],
            )
        )

        if not isinstance(created_user, UserResponseDto):
            logger.critical(f"{log(user)} Failed to create Remnawave user")
            raise ValueError

        logger.info(f"{log(user)} Remnawave user created successfully")
        return created_user

    async def updated_user(
        self,
        user: UserDto,
        plan: PlanSnapshotDto,
        uuid: UUID,
        reset_traffic: bool = True,
    ) -> UserResponseDto:
        logger.info(f"{log(user)} Updating Remnawave user '{uuid}' for plan '{plan.name}'")

        updated_user = await self.remnawave.users.update_user(
            UpdateUserRequestDto(
                uuid=uuid,
                active_internal_squads=[str(uid) for uid in plan.squad_ids],
                description=user.remna_description,
                expire_at=format_days_to_datetime(plan.duration),
                hwidDeviceLimit=format_device_count(plan.device_limit),
                status=SubscriptionStatus.ACTIVE,
                # tag=,
                telegram_id=user.telegram_id,
                traffic_limit_bytes=format_gb_to_bytes(plan.traffic_limit),
                # traffic_limit_strategy=,
            )
        )
        if reset_traffic:
            logger.info(f"{log(user)} Reseted traffic for Remnawave user '{uuid}'")
            await self.remnawave.users.reset_user_traffic(str(uuid))

        if not isinstance(updated_user, UserResponseDto):
            logger.critical(f"{log(user)} Failed to update Remnawave user '{uuid}'")
            raise ValueError

        logger.info(f"{log(user)} Remnawave user '{uuid}' updated successfully")
        return updated_user

    async def delete_user(self, user: UserDto) -> bool:
        logger.info(f"{log(user)} Deleting Remnawave user '{user.telegram_id}'")

        if not user.current_subscription:
            logger.warning(
                f"{log(user)} Cannot delete Remnawave user. No current subscription found"
            )
            return False

        result = await self.remnawave.users.delete_user(
            uuid=user.current_subscription.user_remna_id,
        )

        if not isinstance(result, DeleteUserResponseDto):
            logger.critical(
                f"{log(user)} Remnawave API returned unexpected result while deleting user"
            )
            raise ValueError

        if result.is_deleted:
            logger.info(f"{log(user)} Remnawave user deleted successfully")
        else:
            logger.warning(f"{log(user)} Remnawave user deletion failed")

        return result.is_deleted

    async def handle_user_event(self, event: str, remna_user: RemnaUserDto) -> None:
        from src.infrastructure.taskiq.tasks.subscriptions import (  # noqa: PLC0415
            delete_current_subscription_task,
            sync_current_subscription_task,
            update_status_current_subscription_task,
        )

        logger.info(f"Handling user event '{event}' for user '{remna_user.uuid}'")

        if not remna_user.username.startswith(REMNASHOP_PREFIX):
            logger.debug(
                f"Skipping user {remna_user.username}. "
                f"Username does not start with '{REMNASHOP_PREFIX}' prefix"
            )
            return

        i18n_kwargs = {
            "uuid": str(remna_user.uuid),
            "telegram_id": str(remna_user.telegram_id),
            "status": remna_user.status,
            "traffic_used": i18n_format_bytes_to_unit(remna_user.used_traffic_bytes),
            "traffic_limit": (
                i18n_format_bytes_to_unit(remna_user.traffic_limit_bytes)
                if remna_user.traffic_limit_bytes > 0
                else i18n_format_limit(-1)
            ),
            "device_limit": (
                i18n_format_limit(remna_user.hwid_device_limit)
                if remna_user.hwid_device_limit
                else i18n_format_limit(-1)
            ),
            "expire_at": remna_user.expire_at,
        }

        if event == RemnaUserEvent.MODIFIED:
            logger.debug(f"User '{remna_user.uuid}' modified externally")
            await sync_current_subscription_task.kiq(remna_user)

        elif event == RemnaUserEvent.DELETED:
            logger.debug(f"User '{remna_user.uuid}' deleted in Remnawave")
            await delete_current_subscription_task.kiq(user_telegram_id=remna_user.telegram_id)

        elif event in {
            RemnaUserEvent.REVOKED,
            RemnaUserEvent.ENABLED,
            RemnaUserEvent.DISABLED,
            RemnaUserEvent.LIMITED,
            RemnaUserEvent.EXPIRED,
        }:
            logger.debug(f"User '{remna_user.uuid}' status changed to '{remna_user.status}'")
            await update_status_current_subscription_task.kiq(
                user_telegram_id=remna_user.telegram_id,
                status=SubscriptionStatus(remna_user.status),
            )
            if event == RemnaUserEvent.LIMITED:
                await send_subscription_limited_notification_task.kiq(
                    remna_user=remna_user,
                    i18n_kwargs=i18n_kwargs,
                )
            elif event == RemnaUserEvent.EXPIRED:
                await send_subscription_expire_notification_task.kiq(
                    remna_user=remna_user,
                    ntf_type=event,
                    i18n_kwargs=i18n_kwargs,
                )

        elif event == RemnaUserEvent.FIRST_CONNECTED:
            logger.debug(f"User '{remna_user.uuid}' connected for the first time")
            await send_system_notification_task.kiq(
                ntf_type=SystemNotificationType.USER_FIRST_CONNECTED,
                i18n_key="ntf-event-user-first-connected",
                i18n_kwargs=i18n_kwargs,
            )

        elif event in {
            RemnaUserEvent.EXPIRES_IN_72_HOURS,
            RemnaUserEvent.EXPIRES_IN_48_HOURS,
            RemnaUserEvent.EXPIRES_IN_24_HOURS,
        }:
            logger.debug(f"Sending expiration notification for event '{event}'")
            expire_map = {
                RemnaUserEvent.EXPIRES_IN_72_HOURS: UserNotificationType.EXPIRES_IN_3_DAYS,
                RemnaUserEvent.EXPIRES_IN_48_HOURS: UserNotificationType.EXPIRES_IN_2_DAYS,
                RemnaUserEvent.EXPIRES_IN_24_HOURS: UserNotificationType.EXPIRES_IN_1_DAYS,
            }
            await send_subscription_expire_notification_task.kiq(
                remna_user=remna_user,
                ntf_type=expire_map[RemnaUserEvent(event)],
                i18n_kwargs=i18n_kwargs,
            )

        elif event == RemnaUserEvent.EXPIRED_24_HOURS_AGO:
            logger.debug(f"User '{remna_user.uuid}' expired 24 hours ago")
            await delete_current_subscription_task.kiq(user_telegram_id=remna_user.telegram_id)

        else:
            logger.warning(f"Unhandled user event '{event}' for user '{remna_user.uuid}'")

    async def handle_device_event(self, event: str, device: RemnaHwidUserDeviceDto) -> None:
        logger.info(f"Handling device event '{event}' for user '{device.user_uuid}'")

        if event == RemnaUserHwidDevicesEvent.ADDED:
            logger.debug(f"Device added for user '{device.user_uuid}': hwid={device.hwid}")
            i18n_key = "ntf-event-user-hwid-added"

        elif event == RemnaUserHwidDevicesEvent.DELETED:
            logger.debug(f"Device deleted for user '{device.user_uuid}': hwid={device.hwid}")
            i18n_key = "ntf-event-user-hwid-deleted"

        else:
            logger.warning(f"Unhandled device event '{event}' for user '{device.user_uuid}'")
            return

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.USER_HWID,
            i18n_key=i18n_key,
            i18n_kwargs={
                "user_uuid": str(device.user_uuid),
                "hwid": device.hwid,
                "platform": device.platform,
                "device_model": device.device_model,
                "os_version": device.os_version,
                "user_agent": device.user_agent,
            },
        )

    async def handle_node_event(self, event: str, node: RemnaNodeDto) -> None:
        logger.info(f"Handling node event '{event}' for node '{node.name}'")

        if event == RemnaNodeEvent.CONNECTION_LOST:
            logger.warning(f"Connection lost for node '{node.name}'")
            i18n_key = "ntf-event-node-connection-lost"

        elif event == RemnaNodeEvent.CONNECTION_RESTORED:
            logger.info(f"Connection restored for node '{node.name}'")
            i18n_key = "ntf-event-node-connection-restored"

        elif event == RemnaNodeEvent.TRAFFIC_NOTIFY:
            # TODO: Temporarily shutting down the node before the traffic is reset
            logger.debug(f"Traffic threshold reached on node '{node.name}'")
            i18n_key = "ntf-event-node-traffic"

        else:
            logger.warning(f"Unhandled node event '{event}' for node '{node.name}'")
            return

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.NODE_STATUS,
            i18n_key=i18n_key,
            i18n_kwargs={
                "country": format_country_code(code=node.country_code),
                "name": node.name,
                "address": node.address,
                "port": str(node.port),
                "traffic_used": i18n_format_bytes_to_unit(node.traffic_used_bytes),
                "traffic_limit": i18n_format_bytes_to_unit(node.traffic_limit_bytes),
                "last_status_message": node.last_status_message or "None",
                "last_status_change": node.last_status_change.strftime(DATETIME_FORMAT)
                if node.last_status_change
                else "None",
            },
        )
