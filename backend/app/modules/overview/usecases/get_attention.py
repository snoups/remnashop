import asyncio
from datetime import timedelta
from typing import Final, Optional

import httpx
from loguru import logger
from pydantic import ValidationError
from remnapy import RemnawaveSDK
from remnapy.exceptions import ApiError

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BackupKind, BackupRunStatus
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.backups import BackupRepository
from app.modules.overview.dto import AttentionDto, AttentionItemDto, AttentionKind
from app.modules.settings import (
    BotSettingsDto,
    BotStatusDto,
    SettingsRepository,
    fetch_bot_status,
)
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import TransactionRepository, TransactionStatsRepository

_FAILED_SPIKE: Final[int] = 5
_FAILED_WINDOW: Final[timedelta] = timedelta(hours=1)
_UNFULFILLED_AFTER: Final[timedelta] = timedelta(minutes=10)
_UNFULFILLED_WINDOW: Final[timedelta] = timedelta(days=7)
# checkout orders expire after 30 min, so this has to be shorter to ever fire
_STALE_PENDING_AFTER: Final[timedelta] = timedelta(minutes=15)
_BOT_ERROR_WINDOW: Final[timedelta] = timedelta(hours=1)
_EXPIRING_WITHIN: Final[timedelta] = timedelta(days=7)
_EXPIRING_URGENT: Final[timedelta] = timedelta(hours=24)

_ORDER: Final[tuple[AttentionKind, ...]] = (
    AttentionKind.NODE_OFFLINE,
    AttentionKind.GATEWAY_FAILURES,
    AttentionKind.BACKUP_FAILED,
    AttentionKind.PAID_NOT_FULFILLED,
    AttentionKind.STALE_PENDING,
    AttentionKind.EXPIRING_PAID,
    AttentionKind.BOT_WEBHOOK,
)


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
        uow: UnitOfWork,
    ) -> None:
        self._remnawave_sdk = remnawave_sdk
        self._transaction_repository = transaction_repository
        self._transaction_stats = transaction_stats
        self._backup_repository = backup_repository
        self._subscription_stats = subscription_stats
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> AttentionDto:
        perms = PermissionPolicy.effective_permissions(actor)
        items: list[AttentionItemDto] = []
        async with self._uow:
            items += await self._gateway_failures(perms)
            items += await self._backup_failed(perms)
            items += await self._paid_not_fulfilled(perms)
            items += await self._stale_pending(perms)
            items += await self._expiring_paid(perms)
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
            return []
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
