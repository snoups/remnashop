from decimal import ROUND_HALF_UP, Decimal
from typing import Union

from remnapy.enums import TrafficLimitStrategy
from remnapy.models import UserResponseDto
from remnapy.models.webhook import UserDto as WebhookUserDto

from app.core.constants import GB_TO_BYTES
from app.core.enums import AddOnType
from app.modules.subscriptions.dto import (
    PanelConfigDto,
    SubscriptionConfigUpdateDto,
    SubscriptionDto,
)


def panel_config(user: Union[UserResponseDto, WebhookUserDto]) -> PanelConfigDto:
    return PanelConfigDto(
        url=user.subscription_url,
        traffic_limit=int(
            (Decimal(str(user.traffic_limit_bytes)) / GB_TO_BYTES).quantize(
                Decimal(1), rounding=ROUND_HALF_UP
            )
        ),
        device_limit=user.hwid_device_limit or 0,
        traffic_limit_strategy=TrafficLimitStrategy(user.traffic_limit_strategy),
        tag=user.tag,
        internal_squads=[squad.uuid for squad in user.active_internal_squads],
        external_squad=user.external_squad_uuid,
    )


def _base_limit(panel_limit: int, bonus: int) -> tuple[int, bool]:
    """(base limit, whether the add-ons are dropped) for an effective panel limit.

    The row keeps the plan's limit and add-ons sit on top. 0 is unlimited, so
    add-ons have nothing to add. A panel limit at or below the add-ons is an
    admin's override of the whole limit: it becomes the base and the add-ons go.
    """
    if panel_limit == 0 or bonus == 0:
        return panel_limit, False
    if panel_limit > bonus:
        return panel_limit - bonus, False
    return panel_limit, True


def config_update(
    subscription: SubscriptionDto, config: PanelConfigDto
) -> SubscriptionConfigUpdateDto:
    bonus = {
        addon_type: sum(e.amount for e in subscription.addon_entitlements if e.type is addon_type)
        for addon_type in AddOnType
    }
    traffic, drop_traffic = _base_limit(config.traffic_limit, bonus[AddOnType.TRAFFIC])
    devices, drop_devices = _base_limit(config.device_limit, bonus[AddOnType.DEVICES])
    removed = {AddOnType.TRAFFIC} if drop_traffic else set()
    if drop_devices:
        removed.add(AddOnType.DEVICES)
    return SubscriptionConfigUpdateDto(
        subscription_id=subscription.id,
        url=config.url,
        traffic_limit=traffic,
        device_limit=devices,
        traffic_limit_strategy=config.traffic_limit_strategy,
        tag=config.tag,
        internal_squads=config.internal_squads,
        external_squad=config.external_squad,
        removed_addon_types=frozenset(removed),
    )


def changed_config_fields(
    subscription: SubscriptionDto, update: SubscriptionConfigUpdateDto
) -> list[str]:
    changed = [
        name
        for name in (
            "url",
            "traffic_limit",
            "device_limit",
            "traffic_limit_strategy",
            "tag",
            "external_squad",
        )
        if getattr(subscription, name) != getattr(update, name)
    ]
    if set(subscription.internal_squads) != set(update.internal_squads):
        changed.append("internal_squads")
    if update.removed_addon_types:
        changed.append("addons")
    return changed
