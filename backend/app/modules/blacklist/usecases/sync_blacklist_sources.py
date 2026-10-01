from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.actor import Actor
from app.core.security.permissions import Permission
from app.core.usecase import UseCase

if TYPE_CHECKING:
    # app.modules.users now imports BlacklistRepository (block/unblock usecases) --
    # an eager import here would cycle back into a partially-initialized
    # app.modules.users, same class of fix as core/usecase.py and core/events.py.
    pass


class SyncBlacklistSourcesUseCase(UseCase[None, None]):
    required_permission = Permission.BLACKLIST_SYNC

    async def _execute(self, actor: Actor, data: None) -> None:
        # Deferred: app.modules.blacklist.tasks imports app.worker.broker, a
        # module-level singleton that must not load into the api/telegram
        # processes -- this usecase is imported eagerly there, unlike the
        # task, which only runs in the worker process.
        from app.modules.blacklist.tasks import sync_blacklist_sources_task  # noqa: PLC0415

        await sync_blacklist_sources_task.kiq()  # type: ignore[call-overload]
