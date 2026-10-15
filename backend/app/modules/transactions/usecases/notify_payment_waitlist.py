from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.usecase import UseCase
from app.modules.notifications import SendTelegramTextsDto, SendTelegramTextsUseCase
from app.modules.settings import GetAccessSettingsUseCase
from app.modules.transactions.waitlist_repository import WaitlistClaims

_PAYMENTS_RESTORED_KEY: Final[str] = "ntf-access.payments-restored"
# ~20 s of sending at the Telegram rate while the batch's rows stay locked
_BATCH_SIZE: Final[int] = 500


class NotifyPaymentWaitlistUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        waitlist_claims: WaitlistClaims,
        get_access_settings_use_case: GetAccessSettingsUseCase,
        send_texts_use_case: SendTelegramTextsUseCase,
    ) -> None:
        self._waitlist_claims = waitlist_claims
        self._get_access_settings_use_case = get_access_settings_use_case
        self._send_texts_use_case = send_texts_use_case

    async def _execute(self, actor: Actor, data: None) -> None:
        failed: set[int] = set()
        notified = 0
        while True:
            # the batch's transaction stays open while sending: a concurrent run skips its rows
            async with self._waitlist_claims.batch() as waitlist:
                if not (await self._get_access_settings_use_case.system()).payments_enabled:
                    logger.info("Payments were disabled again, waitlist broadcast stopped")
                    break
                user_ids = await waitlist.claim_batch(_BATCH_SIZE, failed)
                if not user_ids:
                    break
                done = await self._send_texts_use_case.system(
                    SendTelegramTextsDto(user_ids=user_ids, key=_PAYMENTS_RESTORED_KEY)
                )
                # failed sends stay listed for the next re-enable
                await waitlist.remove(done)
            failed |= set(user_ids) - done
            notified += len(done)
            if not done:
                # bot unset, translation missing or Telegram down: the rest would fail too
                logger.warning("Nobody in a waitlist batch was notified, broadcast stopped")
                break
        logger.info(f"Payment waitlist notified: {notified}, failed: {len(failed)}")
