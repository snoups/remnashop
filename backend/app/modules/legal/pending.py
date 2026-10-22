from datetime import datetime
from typing import Final, Optional

from app.core.enums import LegalDocumentKind, Locale, PurchaseChannel
from app.core.utils.time import datetime_now
from app.modules.legal.dto import PendingLegalDocumentsDto
from app.modules.legal.repository import LegalRepository
from app.modules.legal.visibility import visible_documents
from app.modules.translations import TranslationRepository
from app.modules.users import UserDto

# the offer is accepted by paying, never by this gate
GATED_KINDS: Final[frozenset[LegalDocumentKind]] = frozenset(
    {LegalDocumentKind.USER_AGREEMENT, LegalDocumentKind.PRIVACY_POLICY}
)


async def pending_documents(
    repo: LegalRepository,
    *,
    user_id: int,
    user_created_at: datetime,
    channel: PurchaseChannel,
    locale: Optional[Locale],
    default_locale: Locale,
    active_locales: list[Locale],
) -> PendingLegalDocumentsDto:
    revisions = await visible_documents(
        repo,
        await repo.list_documents(),
        channel,
        locale,
        default_locale,
        active_locales,
        kinds=GATED_KINDS,
    )
    pending = []
    is_update = True
    for revision in revisions:
        cutoff = await repo.latest_reacceptance_at(revision.kind, revision.locale, channel)
        if cutoff is not None and cutoff < user_created_at:
            cutoff = None
        accepted = await repo.last_accepted_at(user_id, revision.kind, channel)
        if accepted is None:
            # the cabinet takes its first acceptance at sign-in, asks again only on request
            if channel == PurchaseChannel.CABINET and cutoff is None:
                continue
            is_update = False
        elif cutoff is None or accepted >= cutoff:
            continue
        pending.append(revision)
    return PendingLegalDocumentsDto(documents=pending, is_update=bool(pending) and is_update)


async def pending_for_user(
    repo: LegalRepository,
    translations: TranslationRepository,
    user: UserDto,
    channel: PurchaseChannel,
    locale: Optional[Locale],
) -> PendingLegalDocumentsDto:
    return await pending_documents(
        repo,
        user_id=user.id,
        user_created_at=user.created_at or datetime_now(),
        channel=channel,
        locale=locale,
        default_locale=await translations.get_default_locale(),
        active_locales=await translations.list_active_locales(),
    )
