from typing import ClassVar

from app.core.enums import SessionAudience
from app.core.security.permissions import Permission
from app.modules.notifications.usecases.delete_push_subscription import (
    DeletePushSubscriptionUseCase,
)
from app.modules.notifications.usecases.get_push_public_key import GetPushPublicKeyUseCase
from app.modules.notifications.usecases.list_push_subscriptions import ListPushSubscriptionsUseCase
from app.modules.notifications.usecases.subscribe_push import SubscribePushUseCase

# the same push devices, for a customer: no permission, the cabinet's own sessions


class GetCustomerPushPublicKeyUseCase(GetPushPublicKeyUseCase):
    required_permission = Permission.PUBLIC


class ListCustomerPushSubscriptionsUseCase(ListPushSubscriptionsUseCase):
    required_permission = Permission.PUBLIC
    audience: ClassVar[SessionAudience] = SessionAudience.CABINET


class SubscribeCustomerPushUseCase(SubscribePushUseCase):
    required_permission = Permission.PUBLIC


class DeleteCustomerPushSubscriptionUseCase(DeletePushSubscriptionUseCase):
    required_permission = Permission.PUBLIC
