from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.core.enums import LegalAcceptanceTrigger, LegalDocumentKind, Locale, PurchaseChannel


class LegalTextRequest(BaseModel):
    title: str
    body: str
    requires_reacceptance: bool = False


class LegalTextResponse(BaseModel):
    locale: Locale
    channel: Optional[PurchaseChannel]
    title: str
    body: str
    revision_id: int = Field(validation_alias="id")
    created_at: datetime
    requires_reacceptance: bool
    last_reacceptance_at: Optional[datetime] = None


class LegalDocumentResponse(BaseModel):
    kind: LegalDocumentKind
    show_in_bot: bool
    show_in_cabinet: bool


class LegalTemplateResponse(BaseModel):
    locale: Locale
    title: str
    body: str


class LegalDocumentItemResponse(LegalDocumentResponse):
    texts: list[LegalTextResponse]
    templates: list[LegalTemplateResponse]


class UpdateLegalDocumentRequest(BaseModel):
    show_in_bot: Optional[bool] = None
    show_in_cabinet: Optional[bool] = None


class LegalDocumentsResponse(BaseModel):
    items: list[LegalDocumentItemResponse]
    total: int
    locales: list[Locale]


class PublicLegalDocumentResponse(BaseModel):
    kind: LegalDocumentKind
    title: str
    body: str
    revision_id: int = Field(validation_alias="id")


class LegalDocumentsPublicResponse(BaseModel):
    items: list[PublicLegalDocumentResponse]
    total: int


class PendingLegalDocumentResponse(PublicLegalDocumentResponse):
    created_at: datetime


class PendingLegalResponse(BaseModel):
    items: list[PendingLegalDocumentResponse]
    total: int
    is_update: bool


class AcceptLegalRequest(BaseModel):
    locale: str
    revision_ids: list[int]


class LegalAcceptanceResponse(BaseModel):
    id: int
    kind: LegalDocumentKind
    locale: Locale
    channel: PurchaseChannel
    trigger: LegalAcceptanceTrigger
    transaction_id: Optional[int]
    accepted_at: datetime
    revision_id: int
    title: str

    @model_validator(mode="before")
    @classmethod
    def _flatten_revision(cls, value: Any) -> Any:
        revision = value.revision
        return {
            **{name: getattr(value, name) for name in cls.model_fields if hasattr(value, name)},
            "kind": revision.kind,
            "locale": revision.locale,
            "title": revision.title,
            "revision_id": revision.id,
        }


class LegalAcceptancesResponse(BaseModel):
    items: list[LegalAcceptanceResponse]
    total: int
