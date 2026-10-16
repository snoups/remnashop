from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher, SessionRevoker
from app.modules.account_merge.customer import customer_sides, ensure_customer_mergeable
from app.modules.account_merge.dto import MergeCountsDto
from app.modules.account_merge.events import AccountsMergedEvent
from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.account_merge.rules import merged_user_fields
from app.modules.users import UserDto, UserRepository


class CustomerAccountMerger:
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

    async def _load_other(self, current_id: int, other_id: int) -> UserDto:
        if other_id == current_id:
            raise ValidationError(
                "Cannot merge an account into itself", code=ErrorCode.MERGE_SAME_ACCOUNT
            )
        other = await self._user_repository.find_by_id(other_id)
        if other is None or other.deleted_at:
            raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
        return other

    async def check(self, current: UserDto, other_id: int) -> MergeCountsDto:
        other = await self._load_other(current.id, other_id)
        links = await self._merge_repository.read_links(other.id, current.id)
        ensure_customer_mergeable(current, other, links)
        return await self._merge_repository.count_owned(other_id)

    async def merge(self, current: UserDto, other_id: int, client_ip: str) -> UserDto:
        async with self._uow:
            await self._merge_repository.lock_users([other_id, current.id])
            other = await self._load_other(current.id, other_id)
            fresh = await self._user_repository.find_by_id(current.id)
            if fresh is None or fresh.deleted_at:
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            links = await self._merge_repository.read_links(other.id, fresh.id)
            ensure_customer_mergeable(fresh, other, links)
            sides = customer_sides(fresh, other, links)

            await self._merge_repository.reassign(other.id, fresh.id, sides)
            # the customer's own sessions stay: it is the same person
            await self._session_revoker.revoke_all_by_user(other.id)
            await self._user_repository.anonymize(other.id)
            merged = await self._merge_repository.write_target(
                fresh.id, merged_user_fields(other, fresh, sides)
            )
            await self._event_publisher.publish(
                AccountsMergedEvent(
                    actor=current,
                    target=merged,
                    source=other,
                    choices=dict(sides),
                    ip_address=client_ip,
                )
            )
        logger.info(f"Customer '{fresh.id}' merged user '{other.id}' into themselves")
        return merged
