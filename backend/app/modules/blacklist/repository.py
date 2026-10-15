from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.errors import constraint_name
from app.core.db.models.blacklist import Blacklist
from app.core.db.models.blacklist_source import BlacklistSource
from app.core.db.singleton import SINGLETON_ID, get_or_create_singleton
from app.core.enums import BlacklistKind
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.utils.time import datetime_now
from app.modules.blacklist.dto import (
    AddBlacklistSourceDto,
    BlacklistDto,
    BlacklistOriginDto,
    BlacklistOriginsDto,
    BlacklistSourceDto,
    ParsedSourceList,
)
from app.modules.blacklist.normalize import normalize_identity, removal_key


class BlacklistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_or_create_row(self) -> Blacklist:
        return await get_or_create_singleton(
            self.session, Blacklist, SINGLETON_ID, blocked_telegram_ids=[], blocked_emails=[]
        )

    def _to_source_dto(self, row: BlacklistSource) -> BlacklistSourceDto:
        return BlacklistSourceDto(
            id=row.id,
            url=row.url,
            name=row.name,
            enabled=row.enabled,
            entries_count=row.entries_count,
            last_synced_at=row.last_synced_at,
            last_error=row.last_error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_blacklist(self) -> BlacklistDto:
        row = await self.session.get(Blacklist, SINGLETON_ID)
        if row is None:
            return BlacklistDto()
        return BlacklistDto(
            telegram_ids=list(row.blocked_telegram_ids), emails=list(row.blocked_emails)
        )

    async def add_entry(self, kind: BlacklistKind, value: str) -> bool:
        normalized = normalize_identity(kind, value)
        if normalized is None:
            return False
        row = await self._get_or_create_row()
        if kind is BlacklistKind.TELEGRAM_ID:
            as_int = int(normalized)
            if as_int in row.blocked_telegram_ids:
                return False
            row.blocked_telegram_ids = [*row.blocked_telegram_ids, as_int]
        else:
            if normalized in row.blocked_emails:
                return False
            row.blocked_emails = [*row.blocked_emails, normalized]
        await self.session.flush()
        return True

    async def remove_entry(self, kind: BlacklistKind, value: str) -> bool:
        normalized = removal_key(kind, value)
        if normalized is None:
            return False
        row = await self.session.get(Blacklist, SINGLETON_ID)
        if row is None:
            return False
        if kind is BlacklistKind.TELEGRAM_ID:
            as_int = int(normalized)
            if as_int not in row.blocked_telegram_ids:
                return False
            row.blocked_telegram_ids = [x for x in row.blocked_telegram_ids if x != as_int]
        else:
            if normalized not in row.blocked_emails:
                return False
            row.blocked_emails = [x for x in row.blocked_emails if x != normalized]
        await self.session.flush()
        return True

    async def list_sources(self) -> list[BlacklistSourceDto]:
        rows = (
            await self.session.execute(select(BlacklistSource).order_by(BlacklistSource.id))
        ).scalars()
        return [self._to_source_dto(r) for r in rows]

    async def get_source(self, source_id: int) -> Optional[BlacklistSourceDto]:
        row = await self.session.get(BlacklistSource, source_id)
        return self._to_source_dto(row) if row else None

    async def add_source(self, data: AddBlacklistSourceDto) -> BlacklistSourceDto:
        row = BlacklistSource(
            url=data.url, name=data.name, blocked_telegram_ids=[], blocked_emails=[]
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            if constraint_name(error) != "blacklist_sources_url_key":
                raise
            raise ConflictError(
                f"Blacklist source '{data.url}' already exists",
                code=ErrorCode.BLACKLIST_SOURCE_EXISTS,
            ) from error
        return self._to_source_dto(row)

    async def remove_source(self, source_id: int) -> bool:
        row = await self.session.get(BlacklistSource, source_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True

    async def set_source_enabled(
        self, source_id: int, enabled: bool
    ) -> Optional[BlacklistSourceDto]:
        row = await self.session.get(BlacklistSource, source_id)
        if row is None:
            return None
        row.enabled = enabled
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_source_dto(row)

    async def replace_source_lists(
        self, source_id: int, parsed: ParsedSourceList, *, error: Optional[str]
    ) -> None:
        row = await self.session.get(BlacklistSource, source_id)
        if row is None:
            return
        row.blocked_telegram_ids = list(parsed.telegram_ids)
        row.blocked_emails = list(parsed.emails)
        row.entries_count = len(parsed.telegram_ids) + len(parsed.emails)
        row.last_synced_at = datetime_now()
        row.last_error = error
        await self.session.flush()

    async def mark_source_error(self, source_id: int, error: str) -> None:
        row = await self.session.get(BlacklistSource, source_id)
        if row is None:
            return
        row.last_synced_at = datetime_now()
        row.last_error = error
        await self.session.flush()

    async def is_blacklisted_telegram_id(self, telegram_id: int) -> bool:
        ids, _ = await self.all_blocked_identities()
        return telegram_id in ids

    async def is_blacklisted_email(self, email: str) -> bool:
        normalized = normalize_identity(BlacklistKind.EMAIL, email)
        if normalized is None:
            return False
        _, emails = await self.all_blocked_identities()
        return normalized in emails

    # all_blocked_identities loads every enabled source's full array
    # to answer one membership check. Fine at the current scale (a handful of
    # sources); if a source ever holds >100k ids, switch the two
    # is_blacklisted_* methods to a targeted `WHERE :v = ANY(blocked_telegram_ids)`
    # query with a GIN index and keep all_blocked_identities only for reconcile.
    async def all_blocked_identities(self) -> tuple[set[int], set[str]]:
        manual = await self.session.get(Blacklist, SINGLETON_ID)
        ids: set[int] = set(manual.blocked_telegram_ids) if manual else set()
        emails: set[str] = set(manual.blocked_emails) if manual else set()
        rows = (
            await self.session.execute(
                select(BlacklistSource).where(BlacklistSource.enabled.is_(True))
            )
        ).scalars()
        for row in rows:
            ids.update(row.blocked_telegram_ids)
            emails.update(row.blocked_emails)
        return ids, emails

    async def identity_origins(self) -> BlacklistOriginsDto:
        origins = BlacklistOriginsDto()
        manual = await self.session.get(Blacklist, SINGLETON_ID)
        lists: list[tuple[BlacklistOriginDto, list[int], list[str]]] = []
        if manual:
            lists.append((BlacklistOriginDto(), manual.blocked_telegram_ids, manual.blocked_emails))
        rows = (
            await self.session.execute(
                select(BlacklistSource)
                .where(BlacklistSource.enabled.is_(True))
                .order_by(BlacklistSource.id)
            )
        ).scalars()
        for row in rows:
            origin = BlacklistOriginDto(source_id=row.id, source_name=row.name or row.url)
            lists.append((origin, row.blocked_telegram_ids, row.blocked_emails))
        for origin, telegram_ids, emails in lists:
            for telegram_id in telegram_ids:
                origins.telegram_ids.setdefault(telegram_id, []).append(origin)
            for email in emails:
                origins.emails.setdefault(email, []).append(origin)
        return origins
