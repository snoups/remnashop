from dataclasses import replace

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.account_merge.dto import (
    GetMergePreviewDto,
    MergePreviewDto,
    MergeReferrerCycleDto,
)
from app.modules.account_merge.pair import load_pair
from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.account_merge.rules import (
    compute_conflicts,
    conflicts_fingerprint,
    referrer_candidates,
)
from app.modules.users import UserRepository


class GetMergePreviewUseCase(UseCase[GetMergePreviewDto, MergePreviewDto]):
    required_permission = Permission.USERS_MERGE_PREVIEW

    def __init__(
        self,
        user_repository: UserRepository,
        merge_repository: AccountMergeRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._merge_repository = merge_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetMergePreviewDto) -> MergePreviewDto:
        async with self._uow:
            source, target = await load_pair(
                actor, self._user_repository, data.target_id, data.source_id
            )
            links = await self._merge_repository.read_links(source.id, target.id)
            counts = await self._merge_repository.count_owned(source.id)
            if target.is_privileged:
                # a customer's logins are dropped, not moved, when merging into staff
                counts = replace(counts, passkeys=0, oauth_identities=0)
            conflicts = compute_conflicts(source, target, links)
            pair = {source.id, target.id}
            cycles = [
                MergeReferrerCycleDto(side=side, referrer_id=referrer_id)
                for side, referrer_id in referrer_candidates(source, target, links).items()
                if await self._merge_repository.reaches(referrer_id, pair)
            ]
            return MergePreviewDto(
                source=source,
                target=target,
                conflicts=conflicts,
                referrer_cycles=cycles,
                source_counts=counts,
                fingerprint=conflicts_fingerprint(
                    conflicts,
                    source_privileged=source.is_privileged,
                    target_privileged=target.is_privileged,
                ),
            )
