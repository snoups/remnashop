import asyncio
from datetime import timedelta
from typing import Final, Optional

import httpx
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from remnapy.exceptions import ApiError

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind, BackupRunStatus
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.runtime_heartbeat import read_runtime_heartbeats
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.api_tokens import ApiTokenRepository
from app.modules.backups import BackupRepository
from app.modules.broadcasts import BroadcastRepository
from app.modules.email import read_smtp_failure
from app.modules.event_log import EventOutboxRepository
from app.modules.overview.dto import AttentionDto, AttentionItemDto, AttentionKind
from app.modules.settings import (
    BotSettingsDto,
    BotStatusDto,
    SettingsRepository,
    fetch_bot_status,
)
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import TransactionRepository, TransactionStatsRepository
from app.modules.users import UserRepository

_FAILED_SPIKE: Final[int] = 5
_FAILED_WINDOW: Final[timedelta] = timedelta(hours=1)
_UNFULFILLED_AFTER: Final[timedelta] = timedelta(minutes=10)
_UNFULFILLED_WINDOW: Final[timedelta] = timedelta(days=7)
# checkout orders expire after 30 min, so this has to be shorter to ever fire
_STALE_PENDING_AFTER: Final[timedelta] = timedelta(minutes=15)
_BOT_ERROR_WINDOW: Final[timedelta] = timedelta(hours=1)
_EXPIRING_WITHIN: Final[timedelta] = timedelta(days=7)
_EXPIRING_URGENT: Final[timedelta] = timedelta(hours=24)
_WATCHED_PROCESSES: Final[tuple[str, ...]] = ("worker", "scheduler")
# the sweep runs every minute
_OUTBOX_STUCK_AFTER: Final[timedelta] = timedelta(minutes=5)
# the scheduled check runs hourly
_BACKUP_GRACE: Final[timedelta] = timedelta(hours=2)
_BROADCAST_FAILED_WINDOW: Final[timedelta] = timedelta(days=1)
# the watchdog re-kicks after 5 minutes; still stuck after that means it didn't help
_BROADCAST_STALLED_AFTER: Final[timedelta] = timedelta(minutes=15)
_UNDELIVERABLE_SPIKE: Final[int] = 10
_UNDELIVERABLE_WINDOW: Final[timedelta] = timedelta(days=1)
_TOKEN_EXPIRING_WITHIN: Final[timedelta] = timedelta(days=7)

# enum order is the display order within one severity
_ORDER: Final[tuple[AttentionKind, ...]] = tuple(AttentionKind)


def _bot_needs_attention(status: BotStatusDto) -> bool:
    if not status.webhook_url:
        return True
    if not status.error:
        return False
    # Telegram keeps last_error_message after recovering; no date means the call itself failed
    return status.last_error_at is None or status.last_error_at > datetime_now() - _BOT_ERROR_WINDOW


class GetAttentionUseCase(UseCase[None, AttentionDto]):
    # each item checks its own permission, no single one covers the list
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        remnawave_sdk: RemnawaveSDK,
        transaction_repository: TransactionRepository,
        transaction_stats: TransactionStatsRepository,
        backup_repository: BackupRepository,
        subscription_stats: SubscriptionStatsRepository,
        settings_repository: SettingsRepository,
        broadcast_repository: BroadcastRepository,
        outbox_repository: EventOutboxRepository,
        api_token_repository: ApiTokenRepository,
        user_repository: UserRepository,
        redis: Redis,
        uow: UnitOfWork,
    ) -> None:
        self._remnawave_sdk = remnawave_sdk
        self._transaction_repository = transaction_repository
        self._transaction_stats = transaction_stats
        self._backup_repository = backup_repository
        self._subscription_stats = subscription_stats
        self._settings_repository = settings_repository
        self._broadcast_repository = broadcast_repository
        self._outbox_repository = outbox_repository
        self._api_token_repository = api_token_repository
        self._user_repository = user_repository
        self._redis = redis
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> AttentionDto:
        perms = PermissionPolicy.effective_permissions(actor)
        items: list[AttentionItemDto] = await self._processes_down()
        items += await self._smtp_failed(perms)
        async with self._uow:
            items += await self._outbox_stuck()
            items += await self._gateway_failures(perms)
            items += await self._backup_failed(perms)
            items += await self._backup_overdue(perms)
            items += await self._broadcasts(perms)
            items += await self._email_undeliverable(perms)
            items += await self._api_tokens_expiring(perms)
            items += await self._paid_not_fulfilled(perms)
            items += await self._stale_pending(perms)
            items += await self._expiring_paid(perms)
            items += await self._unrated_anchor_amounts(perms)
            bot_settings = (
                await self._settings_repository.get_bot_settings()
                if Permission.BOT_STATUS_VIEW in perms
                else None
            )
        nodes, bot = await asyncio.gather(self._nodes(perms), self._bot_webhook(bot_settings))
        items += nodes + bot
        items = [i for i in items if i.count > 0]
        items.sort(key=lambda i: (i.severity != "critical", _ORDER.index(i.kind)))
        return AttentionDto(items=items)

    async def _nodes(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.REMNAWAVE_NODES_VIEW not in perms:
            return []
        try:
            nodes = await self._remnawave_sdk.nodes.get_all_nodes()
        except (
            RemnawavePanelUnavailableError,
            ApiError,
            ValidationError,
            httpx.HTTPError,
        ) as error:
            logger.warning(f"Remnawave response unusable: {type(error).__name__}")
            return [
                AttentionItemDto(kind=AttentionKind.PANEL_UNAVAILABLE, severity="critical", count=1)
            ]
        return [
            AttentionItemDto(
                kind=AttentionKind.NODE_OFFLINE,
                severity="critical",
                count=1,
                subject=n.name,
                since=n.last_status_change,
            )
            for n in nodes
            if not n.is_connected and not n.is_disabled
        ]

    async def _bot_webhook(self, bot_settings: Optional[BotSettingsDto]) -> list[AttentionItemDto]:
        if bot_settings is None or not bot_settings.is_configured or not bot_settings.token:
            return []
        status = await fetch_bot_status(bot_settings.token.get_secret_value(), bot_settings.proxy)
        if not _bot_needs_attention(status):
            return []
        return [
            AttentionItemDto(
                kind=AttentionKind.BOT_WEBHOOK, severity="warning", count=1, subject=status.error
            )
        ]

    async def _gateway_failures(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.TRANSACTIONS_VIEW not in perms:
            return []
        failed = await self._transaction_stats.count_failed_by_gateway(
            datetime_now() - _FAILED_WINDOW
        )
        return [
            AttentionItemDto(
                kind=AttentionKind.GATEWAY_FAILURES,
                severity="critical",
                count=count,
                subject=gateway.value,
            )
            for gateway, count in failed.items()
            if count >= _FAILED_SPIKE
        ]

    async def _backup_failed(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.BACKUPS_VIEW not in perms:
            return []
        items = []
        for kind in BackupKind:
            runs, _ = await self._backup_repository.list_runs(kind=kind, page_size=1)
            if runs and runs[0].status == BackupRunStatus.FAILED:
                items.append(
                    AttentionItemDto(
                        kind=AttentionKind.BACKUP_FAILED,
                        severity="critical",
                        count=1,
                        subject=kind.value,
                        since=runs[0].created_at,
                    )
                )
        return items

    async def _paid_not_fulfilled(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.TRANSACTIONS_VIEW not in perms:
            return []
        now = datetime_now()
        stuck = await self._transaction_repository.list_paid_awaiting_reconciliation(
            now - _UNFULFILLED_AFTER, since=now - _UNFULFILLED_WINDOW
        )
        if not stuck:
            return []
        return [
            AttentionItemDto(
                kind=AttentionKind.PAID_NOT_FULFILLED,
                severity="warning",
                count=len(stuck),
                since=min((t.updated_at for t in stuck if t.updated_at), default=None),
            )
        ]

    async def _stale_pending(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.TRANSACTIONS_VIEW not in perms:
            return []
        now = datetime_now()
        count = await self._transaction_stats.count_stale_pending(now - _STALE_PENDING_AFTER, now)
        return [AttentionItemDto(kind=AttentionKind.STALE_PENDING, severity="warning", count=count)]

    async def _expiring_paid(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.SUBSCRIPTIONS_VIEW not in perms:
            return []
        now = datetime_now()
        count, urgent = await self._subscription_stats.count_expiring_paid(
            now, now + _EXPIRING_WITHIN, now + _EXPIRING_URGENT
        )
        return [
            AttentionItemDto(
                kind=AttentionKind.EXPIRING_PAID,
                severity="warning",
                count=count,
                subject=str(urgent),
            )
        ]

    async def _unrated_anchor_amounts(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.TRANSACTIONS_UNRATED_VIEW not in perms:
            return []
        counts = await self._transaction_repository.count_unrated_anchor_amounts()
        return [
            AttentionItemDto(
                kind=AttentionKind.UNRATED_ANCHOR_AMOUNTS,
                severity="warning",
                count=sum(counts.values()),
                subject=", ".join(sorted(counts)),
            )
        ]

    async def _processes_down(self) -> list[AttentionItemDto]:
        alive = {hb.process for hb in await read_runtime_heartbeats(self._redis)}
        return [
            AttentionItemDto(
                kind=AttentionKind.PROCESS_DOWN, severity="critical", count=1, subject=process
            )
            for process in _WATCHED_PROCESSES
            if process not in alive
        ]

    async def _outbox_stuck(self) -> list[AttentionItemDto]:
        stats = await self._outbox_repository.get_stuck_stats(datetime_now() - _OUTBOX_STUCK_AFTER)
        return [
            AttentionItemDto(
                kind=AttentionKind.OUTBOX_STUCK,
                severity="critical",
                count=stats.unprocessed_count,
                since=stats.oldest_occurred_at,
            )
        ]

    async def _smtp_failed(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.EMAIL_SETTINGS_VIEW not in perms:
            return []
        items = []
        for bulk in (False, True):
            failed_at = await read_smtp_failure(self._redis, bulk=bulk)
            if failed_at is not None:
                items.append(
                    AttentionItemDto(
                        kind=AttentionKind.SMTP_FAILED,
                        severity="critical",
                        count=1,
                        subject="bulk" if bulk else "main",
                        since=failed_at,
                    )
                )
        return items

    async def _backup_overdue(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.BACKUPS_VIEW not in perms:
            return []
        settings = await self._backup_repository.get_settings()
        if not settings.enabled:
            return []
        runs, _ = await self._backup_repository.list_runs(kind=BackupKind.DATABASE, page_size=1)
        if runs and runs[0].status == BackupRunStatus.FAILED:
            return []  # backup_failed already says it
        latest = await self._backup_repository.find_latest_completed(BackupKind.DATABASE)
        last_success = latest.finished_at if latest is not None else None
        # never succeeded: counted from when the schedule was switched on
        base = last_success or settings.updated_at
        if (
            base is None
            or datetime_now() - base < timedelta(hours=settings.interval_hours) + _BACKUP_GRACE
        ):
            return []
        return [
            AttentionItemDto(
                kind=AttentionKind.BACKUP_OVERDUE,
                severity="warning",
                count=1,
                since=last_success,
            )
        ]

    async def _broadcasts(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.BROADCASTS_VIEW not in perms:
            return []
        now = datetime_now()
        failed = await self._broadcast_repository.list_failed_since(now - _BROADCAST_FAILED_WINDOW)
        stalled = await self._broadcast_repository.list_stalled_broadcasts(
            now - _BROADCAST_STALLED_AFTER
        )
        return [
            *(
                AttentionItemDto(
                    kind=AttentionKind.BROADCAST_FAILED,
                    severity="critical",
                    count=1,
                    subject=b.title or f"#{b.id}",
                    since=b.updated_at,
                )
                for b in failed
            ),
            *(
                AttentionItemDto(
                    kind=AttentionKind.BROADCAST_STALLED,
                    severity="warning",
                    count=1,
                    subject=b.title or f"#{b.id}",
                    since=b.updated_at,
                )
                for b in stalled
            ),
        ]

    async def _email_undeliverable(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.USERS_VIEW not in perms:
            return []
        count = await self._user_repository.count_email_undeliverable_since(
            datetime_now() - _UNDELIVERABLE_WINDOW
        )
        if count < _UNDELIVERABLE_SPIKE:
            return []
        return [
            AttentionItemDto(
                kind=AttentionKind.EMAIL_UNDELIVERABLE, severity="warning", count=count
            )
        ]

    async def _api_tokens_expiring(self, perms: set[Permission]) -> list[AttentionItemDto]:
        if Permission.API_TOKENS_MANAGE not in perms:
            return []
        now = datetime_now()
        tokens = await self._api_token_repository.list_not_revoked()
        return sorted(
            (
                AttentionItemDto(
                    kind=AttentionKind.API_TOKEN_EXPIRING,
                    severity="warning",
                    count=1,
                    subject=t.name,
                    since=t.expires_at,
                )
                for t in tokens
                if t.expires_at is not None and now < t.expires_at <= now + _TOKEN_EXPIRING_WITHIN
            ),
            key=lambda i: i.since or now,
        )
