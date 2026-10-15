from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.referrals.dto import InvitedUserDto, ListInvitedUsersDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserRepository, get_visible_target, visible_user


class ListInvitedUsersUseCase(UseCase[ListInvitedUsersDto, tuple[list[InvitedUserDto], int]]):
    required_permission = Permission.REFERRALS_INVITED_VIEW

    def __init__(
        self,
        referral_repository: ReferralRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._referral_repository = referral_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListInvitedUsersDto
    ) -> tuple[list[InvitedUserDto], int]:
        async with self._uow:
            await get_visible_target(self._user_repository, actor, data.user_id)
            sees_staff = PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
            entries, total = await self._referral_repository.list_downline(
                data.user_id,
                depth=data.level,
                search=data.search,
                search_staff=sees_staff,
                hide_staff_from=None if sees_staff else actor.id,
                page=data.page,
                page_size=data.page_size,
            )
            referred_ids = [entry.referred_id for entry in entries]
            users = await self._user_repository.list_by_ids(
                list({*referred_ids, *(entry.parent_id for entry in entries)})
            )
            rewards = await self._referral_repository.reward_totals_by_buyer(
                data.user_id, referred_ids
            )
        users_by_id = {user.id: user for user in users}
        items = [
            InvitedUserDto(
                user=visible_user(actor, users_by_id.get(entry.referred_id)),
                via=visible_user(actor, users_by_id.get(entry.parent_id))
                if entry.depth > 1
                else None,
                depth=entry.depth,
                created_at=entry.created_at,
                reward_amounts=rewards.get(entry.referred_id, {}),
            )
            for entry in entries
        ]
        return items, total
