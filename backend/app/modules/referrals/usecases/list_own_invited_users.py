from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import ListOwnInvitedUsersDto, OwnInvitedUserDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto, UserRepository


class ListOwnInvitedUsersUseCase(
    UseCase[ListOwnInvitedUsersDto, tuple[list[OwnInvitedUserDto], int], UserDto]
):
    """The customer's own downline, every level: who, how deep, since when, what they earned them.

    Only the name of each: no ids, usernames or contacts reach another customer, and staff
    stay out of the list as they do in the dashboard's.
    """

    required_permission = Permission.PUBLIC

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
        self, actor: UserDto, data: ListOwnInvitedUsersDto
    ) -> tuple[list[OwnInvitedUserDto], int]:
        async with self._uow:
            entries, total = await self._referral_repository.list_downline(
                actor.id,
                search_staff=False,
                hide_staff_from=actor.id,
                page=data.page,
                page_size=data.page_size,
            )
            referred_ids = [entry.referred_id for entry in entries]
            users = await self._user_repository.list_by_ids(referred_ids)
            rewards = await self._referral_repository.reward_totals_by_buyer(actor.id, referred_ids)
        names = {user.id: user.name for user in users}
        items = [
            OwnInvitedUserDto(
                name=names.get(entry.referred_id),
                level=entry.depth,
                created_at=entry.created_at,
                reward_amounts=rewards.get(entry.referred_id, {}),
            )
            for entry in entries
        ]
        return items, total
