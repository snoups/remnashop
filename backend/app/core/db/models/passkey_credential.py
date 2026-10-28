from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class PasskeyCredential(BaseSql, TimestampMixin):
    __tablename__ = "passkey_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # WebAuthn-generated, base64url; globally unique, so authentication finds
    # the owner without a username (VerifyPasskeyAuthenticationUseCase)
    credential_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary())
    sign_count: Mapped[int]
    transports: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))
    device_type: Mapped[str] = mapped_column(String(32))
    backed_up: Mapped[bool]
    name: Mapped[Optional[str]] = mapped_column(String(100))
    last_used_at: Mapped[Optional[datetime]]
