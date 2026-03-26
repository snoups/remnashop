from datetime import timedelta
from enum import StrEnum
from typing import cast

from loguru import logger
from remnapy.models.webhook import HwidUserDeviceDto, NodeDto

from src.application.common import EventPublisher
from src.application.common.dao import SubscriptionDao, UserDao
from src.application.common.uow import UnitOfWork
from src.application.dto import SubscriptionDto, UserDto
from src.application.events import (
    NodeConnectionLostEvent,
    NodeConnectionRestoredEvent,
    NodeTrafficReachedEvent,
    SubscriptionExpiredEvent,
    SubscriptionExpiresEvent,
    SubscriptionLimitedEvent,
    UserDeviceAddedEvent,
    UserDeviceDeletedEvent,
    UserFirstConnectionEvent,
)
from src.application.events.system import SubscriptionRevokedEvent
from src.application.events.user import SubscriptionExpiredAgoEvent
from src.application.use_cases.remnawave.commands.synchronization import (
    SyncRemnaUser,
    SyncRemnaUserDto,
)
from src.core.constants import DATETIME_FORMAT, IMPORTED_TAG
from src.core.enums import SubscriptionStatus
from src.core.types import RemnaUserDto
from src.core.utils.converters import country_code_to_flag
from src.core.utils.i18n_helpers import (
    i18n_format_bytes_to_unit,
    i18n_format_device_limit,
    i18n_format_expire_time,
)
from src.core.utils.i18n_keys import ByteUnitKey
from src.core.utils.time import datetime_now, get_traffic_reset_delta


class RemnaWebhookService:
    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        event_bus: EventPublisher,
        #
        sync_user: SyncRemnaUser,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.event_bus = event_bus
        #
        self.sync_user = sync_user

    async def handle_user_event(self, event: str, remna_user: RemnaUserDto) -> None:
        logger.debug(f"Received user event '{event}'")
        # TODO: Not connected event

        if not remna_user.telegram_id:
            logger.debug(
                f"Skipping event for RemnaUser '{remna_user.username}': telegram_id is empty"
            )
            return

        if event in {RemnaUserEvent.CREATED, RemnaUserEvent.MODIFIED}:
            await self._process_sync(event, remna_user)
            return

        user = await self.user_dao.get_by_telegram_id(remna_user.telegram_id)
        if not user:
            logger.warning(f"Local user not found with telegram_id '{remna_user.telegram_id}'")
            return

        current_subscription = await self.subscription_dao.get_current(remna_user.telegram_id)
        if not current_subscription:
            logger.warning(
                f"Current subscription not found for telegram_id '{remna_user.telegram_id}', "
                f"status event '{event}' processing aborted"
            )
            return

        if event == RemnaUserEvent.DELETED:
            logger.debug(f"Executing deletion for RemnaUser '{remna_user.telegram_id}'")
            await self._process_delete_subscription(remna_user)

        elif event in {
            RemnaUserEvent.REVOKED,
            RemnaUserEvent.ENABLED,
            RemnaUserEvent.DISABLED,
            RemnaUserEvent.LIMITED,
            RemnaUserEvent.EXPIRED,
        }:
            await self._process_status(user, current_subscription, event, remna_user)

        elif event == RemnaUserEvent.EXPIRED_24_HOURS_AGO:
            await self.event_bus.publish(
                SubscriptionExpiredAgoEvent(
                    user=user,
                    is_trial=current_subscription.is_trial,
                    day=1,
                )
            )

        elif event in {
            RemnaUserEvent.EXPIRES_IN_72_HOURS,
            RemnaUserEvent.EXPIRES_IN_48_HOURS,
            RemnaUserEvent.EXPIRES_IN_24_HOURS,
        }:
            expire_map: dict[str, int] = {
                RemnaUserEvent.EXPIRES_IN_72_HOURS: 3,
                RemnaUserEvent.EXPIRES_IN_48_HOURS: 2,
                RemnaUserEvent.EXPIRES_IN_24_HOURS: 1,
            }
            await self.event_bus.publish(
                SubscriptionExpiresEvent(
                    day=expire_map[event],
                    user=user,
                    is_trial=current_subscription.is_trial,
                )
            )

        elif event == RemnaUserEvent.FIRST_CONNECTED:
            await self.event_bus.publish(
                UserFirstConnectionEvent(
                    telegram_id=user.telegram_id,
                    username=user.username,
                    name=user.name,
                    is_trial=current_subscription.is_trial,
                    subscription_id=remna_user.uuid,
                    subscription_status=SubscriptionStatus(remna_user.status),
                    traffic_used=i18n_format_bytes_to_unit(
                        remna_user.used_traffic_bytes, min_unit=ByteUnitKey.MEGABYTE
                    ),
                    traffic_limit=i18n_format_bytes_to_unit(remna_user.traffic_limit_bytes),
                    device_limit=i18n_format_device_limit(remna_user.hwid_device_limit),
                    expire_time=i18n_format_expire_time(remna_user.expire_at),
                )
            )
        else:
            logger.warning(f"Unhandled user event '{event}' for '{remna_user.telegram_id}'")

    async def handle_device_event(
        self, event: str, remna_user: RemnaUserDto, device: HwidUserDeviceDto
    ) -> None:
        logger.info(f"Received device event '{event}' for RemnaUser '{remna_user.telegram_id}'")

        if not remna_user.telegram_id:
            return

        user = await self.user_dao.get_by_telegram_id(remna_user.telegram_id)
        if not user:
            logger.warning(f"Local user not found for telegram_id '{remna_user.telegram_id}'")
            return

        if event == RemnaUserHwidDevicesEvent.ADDED:
            await self.event_bus.publish(
                UserDeviceAddedEvent(
                    telegram_id=user.telegram_id,
                    username=user.username,
                    name=user.name,
                    hwid=device.hwid,
                    platform=device.platform,
                    device_model=device.device_model,
                    os_version=device.os_version,
                    user_agent=device.user_agent,
                )
            )
        elif event == RemnaUserHwidDevicesEvent.DELETED:
            await self.event_bus.publish(
                UserDeviceDeletedEvent(
                    telegram_id=user.telegram_id,
                    username=user.username,
                    name=user.name,
                    hwid=device.hwid,
                    platform=device.platform,
                    device_model=device.device_model,
                    os_version=device.os_version,
                    user_agent=device.user_agent,
                )
            )

    async def handle_node_event(self, event: str, node: NodeDto) -> None:
        logger.info(f"Received node event '{event}' for node '{node.name}'")

        if event not in {
            RemnaNodeEvent.CONNECTION_LOST,
            RemnaNodeEvent.CONNECTION_RESTORED,
            RemnaNodeEvent.TRAFFIC_NOTIFY,
        }:
            logger.warning(f"Unhandled node event '{event}' for node '{node.name}'")
            return

        if event == RemnaNodeEvent.CONNECTION_LOST:
            await self.event_bus.publish(
                NodeConnectionLostEvent(
                    country=country_code_to_flag(code=node.country_code),
                    name=node.name,
                    address=node.address,
                    port=node.port,
                    traffic_used=i18n_format_bytes_to_unit(node.traffic_used_bytes),
                    traffic_limit=i18n_format_bytes_to_unit(node.traffic_limit_bytes),
                    last_status_message=node.last_status_message,
                    last_status_change=node.last_status_change.strftime(DATETIME_FORMAT)
                    if node.last_status_change
                    else None,
                )
            )
        elif event == RemnaNodeEvent.CONNECTION_RESTORED:
            await self.event_bus.publish(
                NodeConnectionRestoredEvent(
                    country=country_code_to_flag(code=node.country_code),
                    name=node.name,
                    address=node.address,
                    port=node.port,
                    traffic_used=i18n_format_bytes_to_unit(node.traffic_used_bytes),
                    traffic_limit=i18n_format_bytes_to_unit(node.traffic_limit_bytes),
                    last_status_message=node.last_status_message,
                    last_status_change=node.last_status_change.strftime(DATETIME_FORMAT)
                    if node.last_status_change
                    else None,
                )
            )
        elif event == RemnaNodeEvent.TRAFFIC_NOTIFY:
            await self.event_bus.publish(
                NodeTrafficReachedEvent(
                    country=country_code_to_flag(code=node.country_code),
                    name=node.name,
                    address=node.address,
                    port=node.port,
                    traffic_used=i18n_format_bytes_to_unit(node.traffic_used_bytes),
                    traffic_limit=i18n_format_bytes_to_unit(node.traffic_limit_bytes),
                    last_status_message=node.last_status_message,
                    last_status_change=node.last_status_change.strftime(DATETIME_FORMAT)
                    if node.last_status_change
                    else None,
                )
            )

    async def _process_sync(self, event: str, remna_user: RemnaUserDto) -> None:
        if event == RemnaUserEvent.CREATED and remna_user.tag != IMPORTED_TAG:
            logger.debug(
                f"RemnaUser '{remna_user.telegram_id}' ignored: not tagged as '{IMPORTED_TAG}'"
            )
            return

        logger.debug(f"Executing sync for user '{remna_user.telegram_id}' due to event '{event}'")
        dto = SyncRemnaUserDto(remna_user=remna_user, creating=(event == RemnaUserEvent.CREATED))
        await self.sync_user.system(dto)

    async def _process_delete_subscription(self, remna_user: RemnaUserDto) -> None:
        async with self.uow:
            user_telegram_id = cast(int, remna_user.telegram_id)
            subscription = await self.subscription_dao.get_by_remna_id(remna_user.uuid)

            if not subscription:
                logger.warning(
                    f"Subscription not found for UUID '{remna_user.uuid}', delete aborted"
                )
                return

            subscription.status = SubscriptionStatus.DELETED
            await self.subscription_dao.update(subscription)

            current_subscription = await self.subscription_dao.get_current(user_telegram_id)

            if current_subscription:
                if current_subscription.user_remna_id != subscription.user_remna_id:
                    logger.debug(
                        f"Subscription '{subscription.user_remna_id}' "
                        f"is not current for '{user_telegram_id}', skipping unlinking"
                    )
                else:
                    logger.debug(f"Unlinked current subscription for user '{user_telegram_id}'")
                    await self.user_dao.clear_current_subscription(user_telegram_id)

            await self.uow.commit()
            logger.info(f"Successfully processed deletion for subscription '{remna_user.uuid}'")

    async def _process_status(
        self,
        user: UserDto,
        current_subscription: SubscriptionDto,
        event: str,
        remna_user: RemnaUserDto,
    ) -> None:
        await self.sync_user.system(SyncRemnaUserDto(remna_user=remna_user, creating=False))

        if event == RemnaUserEvent.LIMITED:
            await self.event_bus.publish(
                SubscriptionLimitedEvent(
                    user=user,
                    is_trial=current_subscription.is_trial,
                    traffic_strategy=current_subscription.traffic_limit_strategy,
                    reset_time=i18n_format_expire_time(
                        get_traffic_reset_delta(current_subscription.traffic_limit_strategy)
                    ),
                )
            )
        elif event == RemnaUserEvent.EXPIRED:
            if remna_user.expire_at + timedelta(days=3) < datetime_now():
                logger.debug(
                    f"Skipping expiration notification for '{remna_user.telegram_id}': "
                    f"more than 3 days passed"
                )
                return
            await self.event_bus.publish(
                SubscriptionExpiredEvent(user=user, is_trial=current_subscription.is_trial)
            )

        if event == RemnaUserEvent.REVOKED:
            await self.event_bus.publish(
                SubscriptionRevokedEvent(
                    telegram_id=user.telegram_id,
                    username=user.username,
                    name=user.name,
                    is_trial=current_subscription.is_trial,
                    subscription_id=remna_user.uuid,
                    subscription_status=SubscriptionStatus(remna_user.status),
                    traffic_used=i18n_format_bytes_to_unit(
                        remna_user.used_traffic_bytes, min_unit=ByteUnitKey.MEGABYTE
                    ),
                    traffic_limit=i18n_format_bytes_to_unit(remna_user.traffic_limit_bytes),
                    device_limit=i18n_format_device_limit(remna_user.hwid_device_limit),
                    expire_time=i18n_format_expire_time(remna_user.expire_at),
                )
            )


class RemnaUserEvent(StrEnum):
    CREATED = "user.created"
    MODIFIED = "user.modified"
    DELETED = "user.deleted"
    REVOKED = "user.revoked"
    DISABLED = "user.disabled"
    ENABLED = "user.enabled"
    LIMITED = "user.limited"
    EXPIRED = "user.expired"

    TRAFFIC_RESET = "user.traffic_reset"
    NOT_CONNECTED = "user.not_connected"
    FIRST_CONNECTED = "user.first_connected"
    BANDWIDTH_USAGE_THRESHOLD_REACHED = "user.bandwidth_usage_threshold_reached"

    EXPIRES_IN_72_HOURS = "user.expires_in_72_hours"
    EXPIRES_IN_48_HOURS = "user.expires_in_48_hours"
    EXPIRES_IN_24_HOURS = "user.expires_in_24_hours"
    EXPIRED_24_HOURS_AGO = "user.expired_24_hours_ago"


class RemnaUserHwidDevicesEvent(StrEnum):
    ADDED = "user_hwid_devices.added"
    DELETED = "user_hwid_devices.deleted"


class RemnaNodeEvent(StrEnum):
    CREATED = "node.created"
    MODIFIED = "node.modified"
    DISABLED = "node.disabled"
    ENABLED = "node.enabled"
    DELETED = "node.deleted"
    CONNECTION_LOST = "node.connection_lost"
    CONNECTION_RESTORED = "node.connection_restored"
    TRAFFIC_NOTIFY = "node.traffic_notify"


class RemnaServiceEvent(StrEnum):
    PANEL_STARTED = "service.panel_started"
    LOGIN_ATTEMPT_FAILED = "service.login_attempt_failed"
    LOGIN_ATTEMPT_SUCCESS = "service.login_attempt_success"


class RemnaCrmEvent(StrEnum):
    INFRA_BILLING_NODE_PAYMENT_IN_7_DAYS = "crm.infra_billing_node_payment_in_7_days"
    INFRA_BILLING_NODE_PAYMENT_IN_48HRS = "crm.infra_billing_node_payment_in_48hrs"
    INFRA_BILLING_NODE_PAYMENT_IN_24HRS = "crm.infra_billing_node_payment_in_24hrs"
    INFRA_BILLING_NODE_PAYMENT_DUE_TODAY = "crm.infra_billing_node_payment_due_today"
    INFRA_BILLING_NODE_PAYMENT_OVERDUE_24HRS = "crm.infra_billing_node_payment_overdue_24hrs"
    INFRA_BILLING_NODE_PAYMENT_OVERDUE_48HRS = "crm.infra_billing_node_payment_overdue_48hrs"
    INFRA_BILLING_NODE_PAYMENT_OVERDUE_7_DAYS = "crm.infra_billing_node_payment_overdue_7_days"
