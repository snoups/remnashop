from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from remnawave import RemnawaveSDK
from remnawave.models import (
    CreateUserRequestDto,
    DeleteUserHwidDeviceResponseDto,
    DeleteUserResponseDto,
    GetStatsResponseDto,
    GetUserHwidDevicesResponseDto,
    HWIDDeleteRequest,
    HwidUserDeviceDto,
    UpdateUserRequestDto,
    UserResponseDto,
)
from remnawave.models.hwid import HwidDeviceDto
from remnawave.models.webhook import NodeDto

from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.constants import DATETIME_FORMAT
from src.core.enums import (
    RemnaNodeEvent,
    RemnaUserEvent,
    RemnaUserHwidDevicesEvent,
    SubscriptionStatus,
    SystemNotificationType,
    UserNotificationType,
)
from src.core.i18n.keys import ByteUnitKey
from src.core.utils.formatters import (
    format_country_code,
    format_days_to_datetime,
    format_device_count,
    format_gb_to_bytes,
    i18n_format_bytes_to_unit,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.core.utils.message_payload import MessagePayload
from src.core.utils.types import RemnaUserDto
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    UserDto,
)
from src.infrastructure.redis import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import (
    send_subscription_expire_notification_task,
    send_subscription_limited_notification_task,
    send_system_notification_task,
)
from src.services.user import UserService

from .base import BaseService


class RemnawaveService(BaseService):
    remnawave: RemnawaveSDK
    user_service: UserService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        remnawave: RemnawaveSDK,
        user_service: UserService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.remnawave = remnawave
        self.user_service = user_service

    async def try_connection(self) -> None:
        response = await self.remnawave.system.get_stats()

        if not isinstance(response, GetStatsResponseDto):
            if isinstance(response, (bytes, bytearray)):
                response = response.decode(errors="ignore")
            raise ValueError(f"Invalid response from Remnawave panel: {response}")

    async def create_user(
        self,
        user: UserDto,
        plan: PlanSnapshotDto,
        recreate: bool = False,
    ) -> UserResponseDto:
        if recreate:
            remna_user = await self.remnawave.users.get_user_by_username(user.remna_name)

            if isinstance(remna_user, UserResponseDto):
                logger.info(f"Deleting existing Remnawave user '{remna_user.username}'")
                deleted_user = await self.remnawave.users.delete_user(str(remna_user.uuid))

                if isinstance(deleted_user, DeleteUserResponseDto) and deleted_user.is_deleted:
                    logger.info("Existing user deleted successfully")
                else:
                    raise ValueError(f"Could not delete user '{remna_user.username}'")
            else:
                logger.warning("No existing Remnawave user found for recreation")

        logger.info(f"Creating Remnawave user for plan '{plan.name}'")
        created_user = await self.remnawave.users.create_user(
            CreateUserRequestDto(
                expire_at=format_days_to_datetime(plan.duration),
                username=user.remna_name,
                traffic_limit_bytes=format_gb_to_bytes(plan.traffic_limit),
                # traffic_limit_strategy=,
                description=user.remna_description,
                # tag=,
                telegram_id=user.telegram_id,
                hwid_device_limit=format_device_count(plan.device_limit),
                active_internal_squads=plan.internal_squads,
                # external_squad_uuid=,
            )
        )

        if not isinstance(created_user, UserResponseDto):
            raise ValueError("Failed to create Remnawave user: unexpected response")

        logger.info(f"Remnawave user '{created_user.username}' created successfully")
        return created_user

    async def updated_user(
        self,
        user: UserDto,
        uuid: UUID,
        plan: Optional[PlanSnapshotDto] = None,
        subscription: Optional[SubscriptionDto] = None,
        reset_traffic: bool = False,
    ) -> UserResponseDto:
        if subscription:
            status = subscription.status
            traffic_limit = subscription.traffic_limit
            device_limit = subscription.device_limit
            internal_squads = subscription.internal_squads
            expire_at = subscription.expire_at
            logger.info(
                f"Updating Remnawave user '{user.remna_name}' from subscription '{subscription.id}'"
            )
        elif plan:
            status = SubscriptionStatus.ACTIVE
            traffic_limit = plan.traffic_limit
            device_limit = plan.device_limit
            internal_squads = plan.internal_squads
            expire_at = format_days_to_datetime(plan.duration)

            logger.info(f"Updating Remnawave user '{user.remna_name}' from plan '{plan.name}'")
        else:
            raise ValueError("Either 'plan' or 'subscription' must be provided")

        updated_user = await self.remnawave.users.update_user(
            UpdateUserRequestDto(
                uuid=uuid,
                active_internal_squads=internal_squads,
                # external_squad_uuid=,
                description=user.remna_description,
                # tag=,
                expire_at=expire_at,
                hwid_device_limit=format_device_count(device_limit),
                status=status,
                telegram_id=user.telegram_id,
                traffic_limit_bytes=format_gb_to_bytes(traffic_limit),
                # traffic_limit_strategy=,
            )
        )

        if reset_traffic:
            await self.remnawave.users.reset_user_traffic(str(uuid))
            logger.info(f"Traffic reset for user '{user.remna_name}'")

        if not isinstance(updated_user, UserResponseDto):
            raise ValueError("Failed to update Remnawave user: unexpected response")

        logger.info(f"Remnawave user '{user.remna_name}' updated successfully")
        return updated_user

    async def delete_user(self, user: UserDto) -> bool:
        logger.info(f"Deleting Remnawave user '{user.remna_name}'")

        if not user.current_subscription:
            logger.warning(f"No current subscription for user '{user.remna_name}'")
            return False

        result = await self.remnawave.users.delete_user(
            uuid=str(user.current_subscription.user_remna_id),
        )

        if not isinstance(result, DeleteUserResponseDto):
            raise ValueError("Failed to delete Remnawave user: unexpected response")

        if result.is_deleted:
            logger.info(f"Remnawave user '{user.remna_name}' deleted successfully")
        else:
            logger.warning(f"Remnawave user '{user.remna_name}' deletion failed")

        return result.is_deleted

    async def get_devices_user(self, user: UserDto) -> list[HwidDeviceDto]:
        logger.info(f"Fetching devices for Remnawave user '{user.remna_name}'")

        if not user.current_subscription:
            logger.warning(f"No subscription found for user '{user.remna_name}'")
            return []

        result = await self.remnawave.hwid.get_hwid_user(
            uuid=str(user.current_subscription.user_remna_id)
        )

        if not isinstance(result, GetUserHwidDevicesResponseDto):
            raise ValueError("Unexpected response fetching devices")

        if result.total:
            logger.info(f"Found {result.total} device(s) for user '{user.remna_name}'")
            return result.devices

        logger.info(f"No devices found for user '{user.remna_name}'")
        return []

    async def delete_device(self, user: UserDto, hwid: str) -> Optional[int]:
        logger.info(f"Deleting device '{hwid}' for user '{user.remna_name}'")

        if not user.current_subscription:
            logger.warning(f"No subscription found for user '{user.remna_name}'")
            return None

        result = await self.remnawave.hwid.delete_hwid_to_user(
            HWIDDeleteRequest(
                user_uuid=str(user.current_subscription.user_remna_id),
                hwid=hwid,
            )
        )

        if not isinstance(result, DeleteUserHwidDeviceResponseDto):
            raise ValueError("Unexpected response deleting device")

        logger.info(f"Deleted device '{hwid}' for user '{user.remna_name}'")
        return result.total

    async def get_user(self, user: UserDto) -> Optional[UserResponseDto]:
        logger.info(f"Fetching Remnawave user '{user.remna_name}'")
        remna_user = await self.remnawave.users.get_user_by_username(user.remna_name)

        if not isinstance(remna_user, UserResponseDto):
            logger.warning(f"User '{user.remna_name}' not found")
            return None

        logger.info(f"Remnawave user '{user.remna_name}' fetched successfully")
        return remna_user

    async def get_subscription_url(self, user: UserDto) -> Optional[str]:
        remna_user = await self.get_user(user)

        if remna_user is None:
            return None

        return remna_user.subscription_url

    #

    async def handle_user_event(self, event: str, remna_user: RemnaUserDto) -> None:  # noqa: C901
        from src.infrastructure.taskiq.tasks.importer import (  # noqa: PLC0415
            sync_imported_user_task,
        )
        from src.infrastructure.taskiq.tasks.subscriptions import (  # noqa: PLC0415
            delete_current_subscription_task,
            sync_current_subscription_task,
            update_status_current_subscription_task,
        )

        logger.info(f"Received user event '{event}' for user '{remna_user.username}'")

        if not remna_user.telegram_id:
            logger.debug(f"Skipping user '{remna_user.username}': telegram_id is empty")
            return

        if event == RemnaUserEvent.CREATED:
            logger.debug(f"User '{remna_user.username}' created")
            await sync_imported_user_task.kiq(remna_user)
            return

        user = await self.user_service.get(telegram_id=remna_user.telegram_id)

        if not user:
            logger.warning(f"No local user found for telegram_id '{remna_user.telegram_id}'")
            return

        i18n_kwargs = {
            "is_trial": False,
            "user_id": str(user.telegram_id),
            "user_name": user.name,
            "username": user.username or False,
            "subscription_id": str(remna_user.uuid),
            "subscription_status": remna_user.status,
            "traffic_used": i18n_format_bytes_to_unit(
                remna_user.used_traffic_bytes,
                min_unit=ByteUnitKey.MEGABYTE,
            ),
            "traffic_limit": (
                i18n_format_bytes_to_unit(remna_user.traffic_limit_bytes)
                if remna_user.traffic_limit_bytes > 0  # type: ignore[operator]
                else i18n_format_traffic_limit(-1)
            ),
            "device_limit": (
                i18n_format_device_limit(remna_user.hwid_device_limit)
                if remna_user.hwid_device_limit
                else i18n_format_device_limit(-1)
            ),
            "expire_time": i18n_format_expire_time(remna_user.expire_at),  # type: ignore[arg-type]
        }

        if event == RemnaUserEvent.MODIFIED:
            logger.debug(f"User '{remna_user.username}' modified")
            subscription_url = await self.get_subscription_url(user)

            if not subscription_url:
                logger.warning(f"User '{user.telegram_id}' has not subscription_url")
                return

            remna_subscription = RemnaSubscriptionDto.from_remna_user(remna_user.model_dump())
            remna_subscription.url = subscription_url
            await sync_current_subscription_task.kiq(user.telegram_id, remna_subscription)

        elif event == RemnaUserEvent.DELETED:
            logger.debug(f"User '{remna_user.username}' deleted in Remnawave")
            await delete_current_subscription_task.kiq(user_telegram_id=remna_user.telegram_id)

        elif event in {
            RemnaUserEvent.REVOKED,
            RemnaUserEvent.ENABLED,
            RemnaUserEvent.DISABLED,
            RemnaUserEvent.LIMITED,
            RemnaUserEvent.EXPIRED,
        }:
            logger.debug(f"User '{remna_user.username}' status changed to '{remna_user.status}'")
            await update_status_current_subscription_task.kiq(
                user_telegram_id=remna_user.telegram_id,
                status=SubscriptionStatus(remna_user.status),  # type: ignore[arg-type]
            )
            if event == RemnaUserEvent.LIMITED:
                await send_subscription_limited_notification_task.kiq(
                    remna_user=remna_user,
                    i18n_kwargs=i18n_kwargs,
                )
            elif event == RemnaUserEvent.EXPIRED:
                await send_subscription_expire_notification_task.kiq(
                    remna_user=remna_user,
                    ntf_type=UserNotificationType.EXPIRED,
                    i18n_kwargs=i18n_kwargs,
                )

        elif event == RemnaUserEvent.FIRST_CONNECTED:
            logger.debug(f"User '{remna_user.username}' connected for the first time")
            await send_system_notification_task.kiq(
                ntf_type=SystemNotificationType.USER_FIRST_CONNECTED,
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-user-first-connected",
                    i18n_kwargs=i18n_kwargs,
                ),
                reply_markup=get_user_keyboard(user.telegram_id),
            )

        elif event in {
            RemnaUserEvent.EXPIRES_IN_72_HOURS,
            RemnaUserEvent.EXPIRES_IN_48_HOURS,
            RemnaUserEvent.EXPIRES_IN_24_HOURS,
        }:
            logger.debug(f"Sending expiration notification for '{remna_user.username}'")
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
            logger.debug(f"User '{remna_user.username}' expired 24 hours ago")
            await delete_current_subscription_task.kiq(user_telegram_id=remna_user.telegram_id)

        else:
            logger.warning(f"Unhandled user event '{event}' for '{remna_user.username}'")

    async def handle_device_event(
        self,
        event: str,
        remna_user: RemnaUserDto,
        device: HwidUserDeviceDto,
    ) -> None:
        logger.info(f"Received device event '{event}' for user '{remna_user.username}'")

        if not remna_user.telegram_id:
            logger.debug(f"Skipping user '{remna_user.username}': telegram_id is empty")
            return

        user = await self.user_service.get(telegram_id=remna_user.telegram_id)

        if not user:
            logger.warning(f"No local user found for telegram_id '{remna_user.telegram_id}'")
            return

        if event == RemnaUserHwidDevicesEvent.ADDED:
            logger.debug(f"Device '{device.hwid}' added for user '{remna_user.username}'")
            i18n_key = "ntf-event-user-hwid-added"

        elif event == RemnaUserHwidDevicesEvent.DELETED:
            logger.debug(f"Device '{device.hwid}' deleted for user '{remna_user.username}'")
            i18n_key = "ntf-event-user-hwid-deleted"

        else:
            logger.warning(f"Unhandled device event '{event}' for user '{remna_user.username}'")
            return

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.USER_HWID,
            payload=MessagePayload.not_deleted(
                i18n_key=i18n_key,
                i18n_kwargs={
                    "user_id": str(user.telegram_id),
                    "user_name": user.name,
                    "username": user.username or False,
                    "hwid": device.hwid,
                    "platform": device.platform,
                    "device_model": device.device_model,
                    "os_version": device.os_version,
                    "user_agent": device.user_agent,
                },
                reply_markup=get_user_keyboard(user.telegram_id),
            ),
        )

    async def handle_node_event(self, event: str, node: NodeDto) -> None:
        logger.info(f"Received node event '{event}' for node '{node.name}'")

        if event == RemnaNodeEvent.CONNECTION_LOST:
            logger.warning(f"Connection lost for node '{node.name}'")
            i18n_key = "ntf-event-node-connection-lost"

        elif event == RemnaNodeEvent.CONNECTION_RESTORED:
            logger.info(f"Connection restored for node '{node.name}'")
            i18n_key = "ntf-event-node-connection-restored"

        elif event == RemnaNodeEvent.TRAFFIC_NOTIFY:
            # TODO: Temporarily shutting down the node (and plans?) before the traffic is reset
            logger.debug(f"Traffic threshold reached on node '{node.name}'")
            i18n_key = "ntf-event-node-traffic"

        else:
            logger.warning(f"Unhandled node event '{event}' for node '{node.name}'")
            return

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.NODE_STATUS,
            payload=MessagePayload.not_deleted(
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
            ),
        )
