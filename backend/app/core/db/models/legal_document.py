from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import NOW_FUNC, TimestampMixin
from app.core.enums import (
    LegalAcceptanceTrigger,
    LegalDocumentKind,
    Locale,
    PurchaseChannel,
)


class LegalDocument(BaseSql, TimestampMixin):
    __tablename__ = "legal_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[LegalDocumentKind] = mapped_column(unique=True)
    show_in_bot: Mapped[bool] = mapped_column(default=False, server_default="false")
    show_in_cabinet: Mapped[bool] = mapped_column(default=False, server_default="false")


class LegalDocumentRevision(BaseSql):
    __tablename__ = "legal_document_revisions"
    __table_args__ = (Index("ix_legal_revisions_key", "kind", "locale", "channel", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[LegalDocumentKind]
    locale: Mapped[Locale]
    channel: Mapped[Optional[PurchaseChannel]]
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text())
    requires_reacceptance: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW_FUNC)


class LegalAcceptance(BaseSql):
    __tablename__ = "legal_acceptances"
    __table_args__ = (
        Index("ix_legal_acceptances_user_channel_trigger", "user_id", "channel", "trigger"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    revision_id: Mapped[int] = mapped_column(
        ForeignKey("legal_document_revisions.id", ondelete="RESTRICT")
    )
    channel: Mapped[PurchaseChannel]
    trigger: Mapped[LegalAcceptanceTrigger]
    transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW_FUNC)
