from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.dto import BaseDto
from app.core.enums import LegalAcceptanceTrigger, LegalDocumentKind, Locale, PurchaseChannel
from app.modules.users import UserDto


class LegalDocumentDto(BaseDto):
    kind: LegalDocumentKind
    show_in_bot: bool
    show_in_cabinet: bool


class LegalRevisionDto(BaseDto):
    kind: LegalDocumentKind
    locale: Locale
    channel: Optional[PurchaseChannel]
    title: str
    body: str
    requires_reacceptance: bool = False
    created_at: datetime
    # the latest re-acceptance request for this kind, locale and channel, filled for the editor
    last_reacceptance_at: Optional[datetime] = None


class LegalAcceptanceDto(BaseDto):
    user_id: int
    revision: LegalRevisionDto
    channel: PurchaseChannel
    trigger: LegalAcceptanceTrigger
    transaction_id: Optional[int]
    ip_address: Optional[str]
    accepted_at: datetime


@dataclass(frozen=True, kw_only=True)
class CreateLegalRevisionDto:
    kind: LegalDocumentKind
    locale: Locale
    channel: Optional[PurchaseChannel]
    title: str
    body: str
    created_by: Optional[int]
    requires_reacceptance: bool = False


@dataclass(frozen=True, kw_only=True)
class CreateLegalAcceptanceDto:
    user_id: int
    revision_id: int
    channel: PurchaseChannel
    trigger: LegalAcceptanceTrigger
    transaction_id: Optional[int]
    ip_address: Optional[str]


@dataclass(frozen=True, kw_only=True)
class PendingLegalDocumentsDto:
    documents: list[LegalRevisionDto]
    # every pending document was accepted before in this channel
    is_update: bool


@dataclass(frozen=True, kw_only=True)
class AcceptLegalDocumentsDto:
    user: UserDto
    channel: PurchaseChannel
    locale: Optional[Locale]
    # the revisions the customer was shown
    revision_ids: list[int]
    client_ip: Optional[str]


@dataclass(frozen=True, kw_only=True)
class LegalTemplateDto:
    kind: LegalDocumentKind
    locale: Locale
    title: str
    body: str


@dataclass(frozen=True, kw_only=True)
class LegalDocumentsDto:
    documents: list[LegalDocumentDto]
    texts: list[LegalRevisionDto]
    templates: list[LegalTemplateDto]
    locales: list[Locale]


@dataclass(frozen=True, kw_only=True)
class UpdateLegalDocumentDto:
    kind: LegalDocumentKind
    show_in_bot: Optional[bool]
    show_in_cabinet: Optional[bool]
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class SetLegalTextDto:
    kind: LegalDocumentKind
    locale: Locale
    channel: Optional[PurchaseChannel]
    title: str
    body: str
    requires_reacceptance: bool
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class LegalTextKeyDto:
    kind: LegalDocumentKind
    locale: Locale
    channel: Optional[PurchaseChannel]
    client_ip: str
