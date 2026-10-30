import asyncio
import json
from typing import Final, Optional

import requests
from loguru import logger
from pywebpush import WebPushException, webpush

from app.core.constants import TTL_1D
from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience
from app.modules.notifications.dto import PushMessage, PushSubscriptionDto
from app.modules.notifications.repository import NotificationRepository

_TTL_SECONDS: Final[int] = TTL_1D
_TIMEOUT_SECONDS: Final[float] = 10.0
_GONE_STATUSES: Final[frozenset[int]] = frozenset({404, 410})
# our payload was too big, not the device's fault
_PAYLOAD_TOO_LARGE: Final[int] = 413
_DEFAULT_CONTACT: Final[str] = "mailto:admin@localhost"


class WebPushSender:
    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._repository = notification_repository
        self._uow = uow

    async def send(self, user_id: int, message: PushMessage, audience: SessionAudience) -> int:
        async with self._uow:
            settings = await self._repository.get_settings()
            subscriptions = await self._repository.list_push_subscriptions(user_id, audience)
        if settings.vapid_private_key is None or not subscriptions:
            return 0
        private_key = settings.vapid_private_key.get_secret_value()
        contact = settings.vapid_contact or _DEFAULT_CONTACT
        fields = {
            "title": message.title,
            "body": message.body,
            "url": message.url,
            "tag": message.tag,
        }
        if message.icon is not None:
            fields["icon"] = message.icon
        payload = json.dumps(fields)
        delivered = 0
        for subscription in subscriptions:
            status = await self._send_one(subscription, payload, private_key, contact)
            async with self._uow:
                if status is None:
                    await self._repository.record_push_success(subscription.id)
                    delivered += 1
                elif status != _PAYLOAD_TOO_LARGE:
                    await self._repository.record_push_failure(
                        subscription.id, gone=status in _GONE_STATUSES
                    )
        return delivered

    async def _send_one(
        self, subscription: PushSubscriptionDto, payload: str, private_key: str, contact: str
    ) -> Optional[int]:
        """None on success, else the push service's HTTP status (0 when there was none)."""
        # endpoints come from the browser; a redirect could point at an internal host
        session = requests.Session()
        session.max_redirects = 0
        try:
            # pywebpush is sync (requests); one call per device, a thread is enough
            await asyncio.to_thread(
                lambda: webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                    },
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims={"sub": contact},
                    ttl=_TTL_SECONDS,
                    timeout=_TIMEOUT_SECONDS,
                    requests_session=session,
                )
            )
        except WebPushException as error:
            status = error.response.status_code if error.response is not None else 0
            logger.warning(f"Web push to subscription {subscription.id} failed: {status}")
            return status
        except Exception:
            logger.exception(f"Web push to subscription {subscription.id} failed")
            return 0
        finally:
            session.close()
        return None
