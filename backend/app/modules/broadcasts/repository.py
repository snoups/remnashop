import builtins
from datetime import datetime, timedelta
from typing import Any, Final, Optional
from typing import cast as typing_cast

from sqlalchemy import (
    ColumnElement,
    CursorResult,
    Row,
    Select,
    Text,
    case,
    cast,
    delete,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONPATH
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.db.filters import in_ids
from app.core.db.models.ad_link import AdLink
from app.core.db.models.broadcast import Broadcast, BroadcastEmailImage, BroadcastRecipient
from app.core.db.models.plan import Plan
from app.core.db.models.subscription import Subscription
from app.core.db.models.user import User
from app.core.enums import (
    BroadcastCategory,
    BroadcastChannel,
    BroadcastDelivery,
    BroadcastRecipientStatus,
    BroadcastStatus,
    Role,
    SubscriptionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.utils.time import datetime_now, range_end_utc, range_start_utc
from app.modules.broadcasts.audience import (
    audience_predicate,
    channel_condition,
    deliverable_email,
)
from app.modules.broadcasts.dto import (
    AudiencePreviewDto,
    BroadcastAudienceDto,
    BroadcastDto,
    BroadcastRecipientDto,
    BroadcastSummaryDto,
    EmailImageDto,
    ListBroadcastRecipientsDto,
    ListBroadcastsDto,
    PendingEmailRecipientDto,
    PendingRecipientDto,
    RecipientContextDto,
    SaveBroadcastDto,
    SentRecipientDto,
)

NO_TELEGRAM_ERROR: Final[str] = "no telegram"
NO_EMAIL_ERROR: Final[str] = "no email"
UNDELIVERABLE_ERROR: Final[str] = "undeliverable"
OPTED_OUT_ERROR: Final[str] = "opted out"
BLOCKED_ERROR: Final[str] = "blocked"
BOT_BLOCKED_ERROR: Final[str] = "bot blocked"
RECALL_FAILED_ERROR: Final[str] = "recall failed"
SUMMARY_WINDOW: Final[timedelta] = timedelta(days=30)
# only the message texts, so a search for "text" or "_" doesn't hit the JSON keys
_TEXTS_PATH: Final[str] = "$.*.text"
# pg_advisory_xact_lock key: one broadcast starts at a time
_START_LOCK_KEY: Final[int] = 8221941


_PROCESSED: Final[tuple[BroadcastRecipientStatus, ...]] = (
    BroadcastRecipientStatus.SENT,
    BroadcastRecipientStatus.FAILED,
    BroadcastRecipientStatus.BLOCKED,
    BroadcastRecipientStatus.RECALLED,
)


def _channel_conditions(
    delivery: BroadcastDelivery, email_fallback: bool
) -> dict[BroadcastChannel, ColumnElement[bool]]:
    conditions = {
        channel: channel_condition(channel, delivery, email_fallback)
        for channel in BroadcastChannel
    }
    return {channel: c for channel, c in conditions.items() if c is not None}


class BroadcastRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: Broadcast, created_by_name: Optional[str] = None) -> BroadcastDto:
        return BroadcastDto.model_validate(row, from_attributes=True).model_copy(
            update={"created_by_name": created_by_name}
        )

    async def _creator_names(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = await self.session.execute(
            select(User.id, func.coalesce(User.login, User.name)).where(in_ids(User.id, user_ids))
        )
        return dict(rows.tuples().all())

    async def _with_creator(self, row: Broadcast) -> BroadcastDto:
        names = await self._creator_names({row.created_by} if row.created_by is not None else set())
        return self._to_dto(row, names.get(row.created_by) if row.created_by is not None else None)

    @staticmethod
    def _values(data: SaveBroadcastDto) -> dict[str, Any]:
        return {
            "title": (data.title or "").strip() or None,
            "category": data.category,
            "audience": data.audience.model_dump(mode="json"),
            "default_locale": data.default_locale,
            "contents": {
                locale.value: content.model_dump(mode="json")
                for locale, content in data.contents.items()
            },
            "buttons": [button.model_dump(mode="json") for button in data.buttons],
            "promocode_id": data.promocode_id,
            "post_to_channel": data.post_to_channel,
            "delivery": data.delivery,
            "email_fallback": data.email_fallback,
            "email_contents": {
                locale.value: content.model_dump(mode="json")
                for locale, content in data.email_contents.items()
            },
        }

    async def _get_row(self, broadcast_id: int) -> Broadcast:
        row = await self.session.get(Broadcast, broadcast_id)
        if row is None:
            raise NotFoundError(
                f"Broadcast '{broadcast_id}' not found", code=ErrorCode.BROADCAST_NOT_FOUND
            )
        return row

    async def create(self, data: SaveBroadcastDto, created_by: Optional[int]) -> BroadcastDto:
        row = Broadcast(status=BroadcastStatus.DRAFT, created_by=created_by, **self._values(data))
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return await self._with_creator(row)

    async def find_by_id(self, broadcast_id: int) -> Optional[BroadcastDto]:
        # fresh read: the worker re-checks status written by another process
        row = await self.session.get(Broadcast, broadcast_id, populate_existing=True)
        return await self._with_creator(row) if row is not None else None

    async def get_by_id(self, broadcast_id: int) -> BroadcastDto:
        return await self._with_creator(await self._get_row(broadcast_id))

    async def has_missing_references(self, audience: BroadcastAudienceDto) -> bool:
        for model, ids in (
            (Plan, audience.plan_ids),
            (AdLink, audience.ad_link_ids),
            (User, audience.user_ids),
        ):
            unique = set(ids)
            if not unique:
                continue
            found = await self.session.scalar(
                select(func.count()).select_from(model).where(in_ids(model.id, unique))
            )
            if (found or 0) != len(unique):
                return True
        return False

    async def get_by_id_for_update(self, broadcast_id: int) -> BroadcastDto:
        row = await self.session.scalar(
            select(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise NotFoundError(
                f"Broadcast '{broadcast_id}' not found", code=ErrorCode.BROADCAST_NOT_FOUND
            )
        return self._to_dto(row)

    async def try_lock(self, broadcast_id: int) -> Optional[BroadcastDto]:
        row = await self.session.scalar(
            select(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        return self._to_dto(row) if row is not None else None

    async def replace(self, broadcast_id: int, data: SaveBroadcastDto) -> BroadcastDto:
        row = await self._get_row(broadcast_id)
        for key, value in self._values(data).items():
            setattr(row, key, value)
        row.status = BroadcastStatus.DRAFT
        row.scheduled_at = None
        row.updated_at = datetime_now()
        await self.session.flush()
        return await self._with_creator(row)

    async def delete(self, broadcast_id: int) -> None:
        await self.session.delete(await self._get_row(broadcast_id))
        await self.session.flush()

    def _to_email_image_dto(self, row: BroadcastEmailImage) -> EmailImageDto:
        return EmailImageDto.model_validate(row, from_attributes=True)

    async def add_email_image(
        self, broadcast_id: int, content_type: str, extension: str, size: int
    ) -> EmailImageDto:
        row = BroadcastEmailImage(
            broadcast_id=broadcast_id,
            content_type=content_type,
            extension=extension,
            size_bytes=size,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_email_image_dto(row)

    async def list_email_images(self, broadcast_id: int) -> list[EmailImageDto]:
        rows = await self.session.scalars(
            select(BroadcastEmailImage)
            .where(BroadcastEmailImage.broadcast_id == broadcast_id)
            .order_by(BroadcastEmailImage.id)
        )
        return [self._to_email_image_dto(row) for row in rows]

    async def find_email_image(self, broadcast_id: int, image_id: int) -> Optional[EmailImageDto]:
        row = await self.session.scalar(
            select(BroadcastEmailImage).where(
                BroadcastEmailImage.broadcast_id == broadcast_id,
                BroadcastEmailImage.id == image_id,
            )
        )
        return None if row is None else self._to_email_image_dto(row)

    async def delete_email_images(self, ids: list[int]) -> None:
        await self.session.execute(
            delete(BroadcastEmailImage).where(in_ids(BroadcastEmailImage.id, ids))
        )

    async def update_fields(self, broadcast_id: int, **values: object) -> None:
        await self.session.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(**values, updated_at=datetime_now())
            .execution_options(synchronize_session="fetch")
        )

    async def count_audience(
        self,
        audience: BroadcastAudienceDto,
        category: BroadcastCategory,
        delivery: BroadcastDelivery,
        email_fallback: bool,
        now: datetime,
    ) -> AudiencePreviewDto:
        predicate = audience_predicate(audience, category, now)
        channels = _channel_conditions(delivery, email_fallback)
        by_channel: dict[BroadcastChannel, int] = {}
        for channel, condition in channels.items():
            count = await self.session.scalar(select(func.count()).where(predicate, condition))
            by_channel[channel] = count or 0
        rows = await self.session.execute(
            select(User.language, func.count())
            .where(predicate, or_(*channels.values()))
            .group_by(User.language)
        )
        by_locale = dict(rows.tuples().all())
        return AudiencePreviewDto(
            total=sum(by_locale.values()), by_locale=by_locale, by_channel=by_channel
        )

    async def materialize(
        self,
        broadcast_id: int,
        audience: BroadcastAudienceDto,
        category: BroadcastCategory,
        delivery: BroadcastDelivery,
        email_fallback: bool,
        now: datetime,
    ) -> int:
        predicate = audience_predicate(audience, category, now)
        for channel, condition in _channel_conditions(delivery, email_fallback).items():
            source = (
                select(
                    literal(broadcast_id),
                    User.id,
                    literal(BroadcastRecipientStatus.PENDING, type_=BroadcastRecipient.status.type),
                    literal(channel, type_=BroadcastRecipient.channel.type),
                )
                .where(predicate, condition)
                .order_by(User.id)
            )
            await self.session.execute(
                pg_insert(BroadcastRecipient)
                .from_select(["broadcast_id", "user_id", "status", "channel"], source)
                .on_conflict_do_nothing(constraint="uq_broadcast_recipients_user_channel")
            )
        total = await self.session.scalar(
            select(func.count()).where(BroadcastRecipient.broadcast_id == broadcast_id)
        )
        return int(total or 0)

    async def _drop_unreachable(
        self,
        recipient_ids: builtins.list[int],
        marketing: bool,
        unreachable: builtins.list[tuple[ColumnElement[bool], str]],
        refused: builtins.list[tuple[ColumnElement[bool], str]],
    ) -> None:
        # audience was built at materialization; a block or opt-out since then
        # still wins. Only the batch about to go out is checked, so the cost per
        # batch stays flat however large the broadcast is.
        cancel = [(User.is_blocked.is_(True), BLOCKED_ERROR)]
        if marketing:
            cancel.append((User.marketing_opt_out.is_(True), OPTED_OUT_ERROR))
        for status, conditions in (
            (BroadcastRecipientStatus.CANCELED, cancel),
            (BroadcastRecipientStatus.FAILED, unreachable),
            (BroadcastRecipientStatus.BLOCKED, refused),
        ):
            for condition, error in conditions:
                await self.session.execute(
                    update(BroadcastRecipient)
                    .where(
                        in_ids(BroadcastRecipient.id, recipient_ids),
                        BroadcastRecipient.status == BroadcastRecipientStatus.PENDING,
                        BroadcastRecipient.user_id == User.id,
                        condition,
                    )
                    .values(status=status, error=error)
                    .execution_options(synchronize_session=False)
                )

    def _claimable(
        self, broadcast_id: int, channel: BroadcastChannel, limit: int, now: datetime
    ) -> Select[tuple[int]]:
        return (
            select(BroadcastRecipient.id)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.channel == channel,
                BroadcastRecipient.status == BroadcastRecipientStatus.PENDING,
                or_(
                    BroadcastRecipient.claimed_until.is_(None),
                    BroadcastRecipient.claimed_until < now,
                ),
            )
            .order_by(BroadcastRecipient.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

    async def _claim(
        self,
        broadcast_id: int,
        channel: BroadcastChannel,
        limit: int,
        lease: timedelta,
        marketing: bool,
        unreachable: builtins.list[tuple[ColumnElement[bool], str]],
        refused: builtins.list[tuple[ColumnElement[bool], str]],
        contact: InstrumentedAttribute[Any],
    ) -> builtins.list[Row[Any]]:
        now = datetime_now()
        # a batch whose every recipient turned unreachable claims nothing: take
        # the next one, so the chain doesn't stop while rows are still pending
        while True:
            candidates = list(
                await self.session.scalars(self._claimable(broadcast_id, channel, limit, now))
            )
            if not candidates:
                return []
            await self._drop_unreachable(candidates, marketing, unreachable, refused)
            rows = (
                await self.session.execute(
                    update(BroadcastRecipient)
                    .where(
                        in_ids(BroadcastRecipient.id, candidates),
                        BroadcastRecipient.status == BroadcastRecipientStatus.PENDING,
                        User.id == BroadcastRecipient.user_id,
                    )
                    .values(claimed_until=now + lease)
                    .returning(
                        BroadcastRecipient.id,
                        BroadcastRecipient.user_id,
                        contact,
                        BroadcastRecipient.attempts,
                    )
                    .execution_options(synchronize_session=False)
                )
            ).all()
            if rows:
                return sorted(rows, key=lambda r: r[0])

    async def claim_pending(
        self, broadcast_id: int, limit: int, lease: timedelta, *, marketing: bool
    ) -> builtins.list[PendingRecipientDto]:
        rows = await self._claim(
            broadcast_id,
            BroadcastChannel.TELEGRAM,
            limit,
            lease,
            marketing,
            # a user who lost their telegram_id since materialization can never be reached
            [(User.telegram_id.is_(None), NO_TELEGRAM_ERROR)],
            [(User.is_bot_blocked.is_(True), BOT_BLOCKED_ERROR)],
            User.telegram_id,
        )
        return [
            PendingRecipientDto(id=r[0], user_id=r[1], telegram_id=r[2], attempts=r[3])
            for r in rows
        ]

    async def claim_pending_email(
        self, broadcast_id: int, limit: int, lease: timedelta, *, marketing: bool
    ) -> builtins.list[PendingEmailRecipientDto]:
        rows = await self._claim(
            broadcast_id,
            BroadcastChannel.EMAIL,
            limit,
            lease,
            marketing,
            [
                (User.email.is_(None), NO_EMAIL_ERROR),
                (User.email_undeliverable_at.is_not(None), UNDELIVERABLE_ERROR),
            ],
            [],
            User.email,
        )
        return [
            PendingEmailRecipientDto(id=r[0], user_id=r[1], email=r[2], attempts=r[3]) for r in rows
        ]

    async def release_claims(self, ids: builtins.list[int]) -> None:
        await self.session.execute(
            update(BroadcastRecipient)
            .where(in_ids(BroadcastRecipient.id, ids))
            .values(claimed_until=None)
        )

    async def mark_recipient(
        self,
        recipient_id: int,
        status: BroadcastRecipientStatus,
        *,
        message_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        values: dict[str, Any] = {"status": status}
        if status is BroadcastRecipientStatus.SENT:
            values["error"] = None
            values["sent_at"] = datetime_now()
            values["telegram_message_id"] = message_id
        if error:
            values["error"] = error[:255]
        await self.session.execute(
            update(BroadcastRecipient).where(BroadcastRecipient.id == recipient_id).values(**values)
        )

    async def mark_recall_failed(self, recipient_id: int, error: str) -> None:
        await self.session.execute(
            update(BroadcastRecipient)
            .where(BroadcastRecipient.id == recipient_id)
            .values(error=f"{RECALL_FAILED_ERROR}: {error}"[:255])
        )

    async def count_recallable(self, broadcast_id: int) -> int:
        # recall failures count too: a repeat clears them first
        count = await self.session.scalar(
            select(func.count())
            .select_from(BroadcastRecipient)
            .join(User, User.id == BroadcastRecipient.user_id)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == BroadcastRecipientStatus.SENT,
                BroadcastRecipient.telegram_message_id.is_not(None),
                User.telegram_id.is_not(None),
            )
        )
        return count or 0

    async def clear_recall_failures(self, broadcast_id: int) -> None:
        await self.session.execute(
            update(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == BroadcastRecipientStatus.SENT,
                BroadcastRecipient.error.startswith(RECALL_FAILED_ERROR),
            )
            .values(error=None)
        )

    async def bump_attempt(self, recipient_id: int, max_attempts: int, error: str) -> None:
        status_type = BroadcastRecipient.status.type
        await self.session.execute(
            update(BroadcastRecipient)
            # an admin cancel in the meantime wins
            .where(
                BroadcastRecipient.id == recipient_id,
                BroadcastRecipient.status == BroadcastRecipientStatus.PENDING,
            )
            .values(
                attempts=BroadcastRecipient.attempts + 1,
                claimed_until=None,
                error=error[:255],
                status=case(
                    (
                        BroadcastRecipient.attempts + 1 >= max_attempts,
                        literal(BroadcastRecipientStatus.FAILED, type_=status_type),
                    ),
                    else_=literal(BroadcastRecipientStatus.PENDING, type_=status_type),
                ),
            )
        )

    async def cancel_pending(self, broadcast_id: int) -> None:
        await self.session.execute(
            update(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == BroadcastRecipientStatus.PENDING,
            )
            .values(status=BroadcastRecipientStatus.CANCELED)
        )

    async def fail_pending(self, broadcast_id: int, error: str) -> None:
        await self.session.execute(
            update(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == BroadcastRecipientStatus.PENDING,
            )
            .values(status=BroadcastRecipientStatus.FAILED, error=error, claimed_until=None)
        )

    async def reset_failed(self, broadcast_id: int) -> int:
        result = await self.session.execute(
            update(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == BroadcastRecipientStatus.FAILED,
            )
            .values(
                status=BroadcastRecipientStatus.PENDING, attempts=0, error=None, claimed_until=None
            )
        )
        return typing_cast(CursorResult[Any], result).rowcount

    async def list_recallable(
        self, broadcast_id: int, limit: int
    ) -> builtins.list[SentRecipientDto]:
        rows = await self.session.execute(
            select(BroadcastRecipient.id, User.telegram_id, BroadcastRecipient.telegram_message_id)
            .join(User, User.id == BroadcastRecipient.user_id)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.status == BroadcastRecipientStatus.SENT,
                BroadcastRecipient.telegram_message_id.is_not(None),
                # a failed delete stays SENT but is skipped, or the chain would loop over it
                BroadcastRecipient.error.is_(None),
                User.telegram_id.is_not(None),
            )
            .order_by(BroadcastRecipient.id)
            .limit(limit)
        )
        return [
            SentRecipientDto(
                id=r.id, telegram_id=r.telegram_id, telegram_message_id=r.telegram_message_id
            )
            for r in rows
        ]

    async def refresh_counts(self, broadcast_id: int) -> BroadcastDto:
        rows = await self.session.execute(
            select(BroadcastRecipient.status, func.count())
            .where(BroadcastRecipient.broadcast_id == broadcast_id)
            .group_by(BroadcastRecipient.status)
        )
        counts = dict(rows.tuples().all())
        row = await self.session.scalar(
            select(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise NotFoundError(
                f"Broadcast '{broadcast_id}' not found", code=ErrorCode.BROADCAST_NOT_FOUND
            )
        row.sent_count = counts.get(BroadcastRecipientStatus.SENT, 0)
        row.failed_count = counts.get(BroadcastRecipientStatus.FAILED, 0)
        row.blocked_count = counts.get(BroadcastRecipientStatus.BLOCKED, 0)
        row.recalled_count = counts.get(BroadcastRecipientStatus.RECALLED, 0)
        row.updated_at = datetime_now()
        await self.session.flush()
        return self._to_dto(row)

    async def has_pending(self, broadcast_id: int) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    select(BroadcastRecipient.id)
                    .where(
                        BroadcastRecipient.broadcast_id == broadcast_id,
                        BroadcastRecipient.status == BroadcastRecipientStatus.PENDING,
                    )
                    .exists()
                )
            )
        )

    async def lock_starts(self) -> None:
        await self.session.execute(select(func.pg_advisory_xact_lock(_START_LOCK_KEY)))

    async def has_sending(self) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    select(Broadcast.id).where(Broadcast.status == BroadcastStatus.SENDING).exists()
                )
            )
        )

    async def next_due(self, now: datetime) -> Optional[int]:
        due: Optional[int] = await self.session.scalar(
            select(Broadcast.id)
            .where(Broadcast.status == BroadcastStatus.SCHEDULED, Broadcast.scheduled_at <= now)
            .order_by(Broadcast.scheduled_at, Broadcast.id)
            .limit(1)
        )
        return due

    async def count_failed_since(self, since: datetime) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(Broadcast)
            .where(Broadcast.status == BroadcastStatus.FAILED, Broadcast.updated_at >= since)
        )
        return count or 0

    async def list_stalled(self, before: datetime) -> builtins.list[int]:
        rows = await self.session.scalars(
            select(Broadcast.id)
            .where(Broadcast.status == BroadcastStatus.SENDING, Broadcast.updated_at < before)
            .order_by(Broadcast.id)
        )
        return builtins.list(rows)

    async def list_recipients(
        self, data: ListBroadcastRecipientsDto
    ) -> tuple[builtins.list[BroadcastRecipientDto], int]:
        conditions: builtins.list[ColumnElement[bool]] = [
            BroadcastRecipient.broadcast_id == data.broadcast_id
        ]
        if data.status is not None:
            conditions.append(BroadcastRecipient.status == data.status)
        if data.channel is not None:
            conditions.append(BroadcastRecipient.channel == data.channel)
        total = await self.session.scalar(
            select(func.count()).select_from(BroadcastRecipient).where(*conditions)
        )
        rows = await self.session.execute(
            select(BroadcastRecipient, User)
            .join(User, User.id == BroadcastRecipient.user_id)
            .where(*conditions)
            .order_by(BroadcastRecipient.id)
            .offset((data.page - 1) * data.page_size)
            .limit(data.page_size)
        )
        return [
            BroadcastRecipientDto(
                id=row.id,
                broadcast_id=row.broadcast_id,
                user_id=row.user_id,
                channel=row.channel,
                status=row.status,
                attempts=row.attempts,
                telegram_message_id=row.telegram_message_id,
                error=row.error,
                sent_at=row.sent_at,
                user_name=user.name,
                username=user.username,
                telegram_id=user.telegram_id,
                email=user.email,
                language=user.language,
            )
            for row, user in rows.tuples()
        ], total or 0

    async def recipient_contexts(
        self, user_ids: builtins.list[int]
    ) -> dict[int, RecipientContextDto]:
        if not user_ids:
            return {}
        live = (
            select(
                Subscription.user_id,
                Subscription.plan_snapshot["name"].as_string().label("plan_name"),
                Subscription.expire_at,
            )
            .where(
                in_ids(Subscription.user_id, user_ids),
                Subscription.status.in_((SubscriptionStatus.ACTIVE, SubscriptionStatus.LIMITED)),
            )
            .order_by(Subscription.user_id, Subscription.expire_at.desc())
            .distinct(Subscription.user_id)
            .subquery()
        )
        rows = await self.session.execute(
            select(User, live.c.plan_name, live.c.expire_at)
            .outerjoin(live, live.c.user_id == User.id)
            .where(in_ids(User.id, user_ids))
        )
        return {
            user.id: RecipientContextDto(
                user_id=user.id,
                name=user.name,
                username=user.username,
                language=user.language,
                bonus_days=user.bonus_days,
                points=int(user.points),
                plan_name=plan_name,
                expire_at=expire_at,
            )
            for user, plan_name, expire_at in rows.tuples()
        }

    async def is_recipient(self, broadcast_id: int, user_id: int) -> bool:
        found = await self.session.scalar(
            select(BroadcastRecipient.id).where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.user_id == user_id,
            )
        )
        return found is not None

    async def prune_recipients(self, completed_before: datetime) -> int:
        result = await self.session.execute(
            delete(BroadcastRecipient).where(
                BroadcastRecipient.broadcast_id.in_(
                    select(Broadcast.id).where(Broadcast.completed_at < completed_before)
                )
            )
        )
        return typing_cast(CursorResult[Any], result).rowcount

    async def channel_post(self, broadcast_id: int) -> Optional[tuple[int, int]]:
        row = (
            await self.session.execute(
                select(Broadcast.channel_chat_id, Broadcast.channel_message_id).where(
                    Broadcast.id == broadcast_id
                )
            )
        ).first()
        if row is None or row.channel_chat_id is None or row.channel_message_id is None:
            return None
        return row.channel_chat_id, row.channel_message_id

    async def list(self, data: ListBroadcastsDto) -> tuple[builtins.list[BroadcastDto], int]:
        conditions: builtins.list[ColumnElement[bool]] = []
        if data.statuses:
            conditions.append(Broadcast.status.in_(data.statuses))
        if data.search:
            texts = cast(
                func.jsonb_path_query_array(Broadcast.contents, cast(_TEXTS_PATH, JSONPATH)), Text
            )
            conditions.append(
                or_(
                    Broadcast.title.icontains(data.search, autoescape=True),
                    texts.icontains(data.search, autoescape=True),
                )
            )
        created_from = range_start_utc(data.created_from)
        created_to = range_end_utc(data.created_to)
        if created_from is not None:
            conditions.append(Broadcast.created_at >= created_from)
        if created_to is not None:
            conditions.append(Broadcast.created_at < created_to)
        total = await self.session.scalar(
            select(func.count()).select_from(Broadcast).where(*conditions)
        )
        rows = await self.session.scalars(
            select(Broadcast)
            .where(*conditions)
            .order_by(Broadcast.created_at.desc(), Broadcast.id.desc())
            .offset((data.page - 1) * data.page_size)
            .limit(data.page_size)
        )
        broadcasts = builtins.list(rows)
        names = await self._creator_names({r.created_by for r in broadcasts if r.created_by})
        return [self._to_dto(row, names.get(row.created_by or 0)) for row in broadcasts], total or 0

    async def summary(self, now: datetime) -> BroadcastSummaryDto:
        since = now - SUMMARY_WINDOW
        counts = dict(
            (
                await self.session.execute(
                    select(Broadcast.status, func.count()).group_by(Broadcast.status)
                )
            )
            .tuples()
            .all()
        )
        next_scheduled = await self.session.scalar(
            select(func.min(Broadcast.scheduled_at)).where(
                Broadcast.status == BroadcastStatus.SCHEDULED
            )
        )
        delivered = await self.session.scalar(
            select(func.count())
            .select_from(BroadcastRecipient)
            .join(Broadcast, Broadcast.id == BroadcastRecipient.broadcast_id)
            .where(
                Broadcast.started_at >= since,
                BroadcastRecipient.status == BroadcastRecipientStatus.SENT,
            )
        )
        processed = await self.session.scalar(
            select(func.count())
            .select_from(BroadcastRecipient)
            .join(Broadcast, Broadcast.id == BroadcastRecipient.broadcast_id)
            .where(
                Broadcast.started_at >= since,
                BroadcastRecipient.status.in_(_PROCESSED),
            )
        )
        customers = (
            User.role == Role.USER,
            User.deleted_at.is_(None),
            User.is_blocked.is_(False),
        )
        reachable = (*customers, or_(User.telegram_id.is_not(None), deliverable_email()))
        reachable_total = await self.session.scalar(select(func.count()).where(*reachable))
        by_email = await self.session.scalar(
            select(func.count()).where(*customers, deliverable_email())
        )
        opted_out = await self.session.scalar(
            select(func.count()).where(*reachable, User.marketing_opt_out.is_(True))
        )
        return BroadcastSummaryDto(
            by_status={status: counts.get(status, 0) for status in BroadcastStatus},
            next_scheduled_at=next_scheduled,
            delivered_30d=delivered or 0,
            processed_30d=processed or 0,
            opted_out=opted_out or 0,
            reachable_customers=reachable_total or 0,
            reachable_by_email=by_email or 0,
        )
