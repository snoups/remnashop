from collections.abc import Callable
from typing import Final, Optional

from remnapy.models.webhook import (
    BillingNodeDto,
    LoginAttemptDto,
    TorrentBlockerReportDto,
    UserHwidDeviceEventDto,
    WebhookNodeDto,
    WebhookPayloadDto,
)
from remnapy.models.webhook import (
    UserDto as WebhookUserDto,
)

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.events import BaseEvent
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import PublishPanelEventDto
from app.modules.subscriptions.events import (
    NodeBillingDueEvent,
    NodeConnectionLostEvent,
    NodeConnectionRestoredEvent,
    NodeTrafficReachedEvent,
    PanelLoginFailedEvent,
    PanelLoginSucceededEvent,
    PanelStartedEvent,
    SubscriptionDeviceAddedEvent,
    SubscriptionDeviceRemovedEvent,
    SubscriptionExpiredAgoEvent,
    SubscriptionExpiredEvent,
    SubscriptionExpiringEvent,
    SubscriptionFirstConnectedEvent,
    SubscriptionNotConnectedEvent,
    SubscriptionRevokedEvent,
    SubscriptionTrafficLimitedEvent,
    SubscriptionTrafficResetEvent,
    SubscriptionTrafficThresholdEvent,
    TorrentBlockerReportEvent,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto, UserRepository

# events whose only payload is the subscription; user.created/modified/deleted
# are echoes of our own panel calls and stay out
_PLAIN_USER_EVENTS: Final[dict[str, Callable[..., BaseEvent]]] = {
    "user.expired": SubscriptionExpiredEvent,
    "user.limited": SubscriptionTrafficLimitedEvent,
    "user.bandwidth_usage_threshold_reached": SubscriptionTrafficThresholdEvent,
    "user.first_connected": SubscriptionFirstConnectedEvent,
    "user.traffic_reset": SubscriptionTrafficResetEvent,
    "user.revoked": SubscriptionRevokedEvent,
}
_NODE_EVENTS: Final[dict[str, Callable[..., BaseEvent]]] = {
    "node.connection_restored": NodeConnectionRestoredEvent,
    "node.traffic_notify": NodeTrafficReachedEvent,
}


def _remnawave_user_id(payload: WebhookPayloadDto) -> Optional[int]:
    data = payload.data
    if isinstance(data, WebhookUserDto):
        return data.id
    if isinstance(data, (UserHwidDeviceEventDto, TorrentBlockerReportDto)):
        return data.user.id
    return None


def _system_event(payload: WebhookPayloadDto) -> Optional[BaseEvent]:
    event, data = payload.event, payload.data
    if isinstance(data, WebhookNodeDto):
        if event == "node.connection_lost":
            return NodeConnectionLostEvent(node_name=data.name, message=data.last_status_message)
        factory = _NODE_EVENTS.get(event)
        return factory(node_name=data.name) if factory else None
    if isinstance(data, LoginAttemptDto):
        # the attempted password is in the payload and never leaves this function
        login_event = (
            PanelLoginSucceededEvent
            if event == "service.login_attempt_success"
            else PanelLoginFailedEvent
        )
        return login_event(username=data.username, user_agent=data.user_agent, ip_address=data.ip)
    if isinstance(data, BillingNodeDto):
        return NodeBillingDueEvent(
            provider=data.provider_name,
            node_name=data.node_name,
            next_billing_at=data.next_billing_at.isoformat(),
        )
    if event == "service.panel_started":
        return PanelStartedEvent()
    return None


def _user_event(
    payload: WebhookPayloadDto, owner: UserDto, subscription_id: int
) -> Optional[BaseEvent]:
    event, data, meta = payload.event, payload.data, payload.meta
    if event == "user.expiration":
        hours = meta.expiration if meta else None
        if not hours:
            # 0 is the moment of expiry, which user.expired already reports
            return None
        if hours > 0:
            return SubscriptionExpiringEvent(
                user=owner, subscription_id=subscription_id, hours=hours
            )
        return SubscriptionExpiredAgoEvent(
            user=owner, subscription_id=subscription_id, hours=-hours
        )
    if event == "user.not_connected":
        hours = meta.not_connected_after_hours if meta else None
        if not hours:
            return None
        return SubscriptionNotConnectedEvent(
            user=owner, subscription_id=subscription_id, hours=hours
        )
    plain = _PLAIN_USER_EVENTS.get(event)
    if plain is not None:
        return plain(user=owner, subscription_id=subscription_id)
    if isinstance(data, UserHwidDeviceEventDto):
        device = data.hwid_user_device
        device_event = (
            SubscriptionDeviceAddedEvent
            if event == "user_hwid_devices.added"
            else SubscriptionDeviceRemovedEvent
        )
        return device_event(
            user=owner,
            subscription_id=subscription_id,
            hwid=device.hwid,
            platform=device.platform,
            device_model=device.device_model,
            os_version=device.os_version,
            ip_address=device.request_ip,
        )
    if isinstance(data, TorrentBlockerReportDto):
        action = data.report.action_report
        return TorrentBlockerReportEvent(
            user=owner,
            subscription_id=subscription_id,
            node_name=data.node.name,
            destination=data.report.xray_report.destination,
            blocked_until=action.will_unblock_at.isoformat(),
            ip_address=action.ip,
        )
    return None


class PublishPanelEventUseCase(UseCase[PublishPanelEventDto, None]):
    # system-only: called from the Remnawave webhook handler
    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: PublishPanelEventDto) -> None:
        payload = data.payload
        system_event = _system_event(payload)
        if system_event is not None:
            async with self._uow:
                await self._event_publisher.publish(system_event)
            return

        remnawave_user_id = _remnawave_user_id(payload)
        if remnawave_user_id is None:
            return
        async with self._uow:
            subscription = await self._subscription_repository.get_by_remnawave_user_id(
                remnawave_user_id
            )
            if subscription is None or subscription.status is SubscriptionStatus.DELETED:
                return
            owner = await self._user_repository.find_by_id(subscription.user_id)
            if owner is None:
                return
            event = _user_event(payload, owner, subscription.id)
            if event is not None:
                await self._event_publisher.publish(event)
