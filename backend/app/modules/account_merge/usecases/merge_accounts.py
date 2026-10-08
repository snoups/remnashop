from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher, SessionRevoker
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.account_merge.dto import MergeAccountsDto
from app.modules.account_merge.events import AccountsMergedEvent
from app.modules.account_merge.pair import load_pair
from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.account_merge.rules import (
    compute_conflicts,
    conflicts_fingerprint,
    merged_user_fields,
    resolve_sides,
)
from app.modules.users import UserDto, UserRepository


class MergeAccountsUseCase(UseCase[MergeAccountsDto, UserDto]):
    required_permission = Permission.USERS_MERGE

    def __init__(
        self,
        user_repository: UserRepository,
        merge_repository: AccountMergeRepository,
        session_revoker: SessionRevoker,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._merge_repository = merge_repository
        self._session_revoker = session_revoker
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: MergeAccountsDto) -> UserDto:
        async with self._uow:
            await self._merge_repository.lock_users([data.source_id, data.target_id])
            source, target = await load_pair(
                actor, self._user_repository, data.target_id, data.source_id
            )
            links = await self._merge_repository.read_links(source.id, target.id)
            conflicts = compute_conflicts(source, target, links)
            fingerprint = conflicts_fingerprint(
                conflicts,
                source_privileged=source.is_privileged,
                target_privileged=target.is_privileged,
            )
            if fingerprint != data.fingerprint:
                raise ValidationError(
                    "Accounts changed since the preview", code=ErrorCode.MERGE_PREVIEW_STALE
                )
            sides = resolve_sides(conflicts, data.choices)

            # customer logins must not open a staff account
            customer = target if source.is_privileged else source if target.is_privileged else None
            await self._merge_repository.reassign(
                source.id,
                target.id,
                sides,
                drop_credentials_of=customer.id if customer else None,
            )
            await self._session_revoker.revoke_all_by_user(source.id)
            if target.id != actor.id:
                await self._session_revoker.revoke_all_by_user(target.id)
            # frees OWNER and every unique column before target takes them
            if source.is_privileged:
                await self._user_repository.demote_from_admin(source.id)
            await self._user_repository.anonymize(source.id)
            merged = await self._merge_repository.write_target(
                target.id, merged_user_fields(source, target, sides)
            )
            await self._event_publisher.publish(
                AccountsMergedEvent(actor=actor, target=merged, source=source, choices=dict(sides))
            )
        logger.info(f"{actor.log} Merged user '{source.id}' into '{target.id}'")
        return merged
