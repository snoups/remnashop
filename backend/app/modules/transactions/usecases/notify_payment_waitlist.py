from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.usecase import UseCase
from app.modules.settings import GetAccessSettingsUseCase
from app.modules.transactions.dto import NotifyPaymentWaitlistDto
from app.modules.transactions.ports import PaymentsRestoredNotifier
from app.modules.transactions.waitlist_repository import WaitlistClaims

# the batch's rows stay locked while its notifications are queued
_BATCH_SIZE: Final[int] = 500


class NotifyPaymentWaitlistUseCase(UseCase[NotifyPaymentWaitlistDto, None]):
    required_permission = None

    def __init__(
        self,
        waitlist_claims: WaitlistClaims,
        get_access_settings_use_case: GetAccessSettingsUseCase,
        notifier: PaymentsRestoredNotifier,
    ) -> None:
        self._waitlist_claims = waitlist_claims
        self._get_access_settings_use_case = get_access_settings_use_case
        self._notifier = notifier

    async def _execute(self, actor: Actor, data: NotifyPaymentWaitlistDto) -> None:
        notified = 0
        while True:
            # the batch's transaction stays open while queueing: a concurrent run skips its rows
            async with self._waitlist_claims.batch() as waitlist:
                if not (await self._get_access_settings_use_case.system()).payments_enabled:
                    logger.info("Payments were disabled again, waitlist broadcast stopped")
                    break
                user_ids = await waitlist.claim_batch(_BATCH_SIZE, set())
                if not user_ids:
                    break
                await self._notifier.notify(user_ids, data.outbox_id)
                await waitlist.remove(set(user_ids))
            notified += len(user_ids)
        logger.info(f"Payment waitlist notified: {notified}")
