from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.modules.account_merge import CustomerAccountMerger
from app.modules.identity_links.linker import IdentityLinker
from app.modules.identity_links.merge_tokens import MergeTokenStore
from app.modules.users import UserDto, UserRepository


def _invalid() -> ConflictError:
    return ConflictError("Merge token is invalid", code=ErrorCode.MERGE_TOKEN_INVALID)


class ConfirmMergeUseCase:
    def __init__(
        self,
        merge_tokens: MergeTokenStore,
        linker: IdentityLinker,
        merger: CustomerAccountMerger,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._merge_tokens = merge_tokens
        self._linker = linker
        self._merger = merger
        self._user_repository = user_repository
        self._uow = uow

    async def execute(self, user: UserDto, token: str, client_ip: str) -> UserDto:
        ticket = await self._merge_tokens.take(token)
        if ticket is None or ticket.user_id != user.id:
            raise _invalid()
        async with self._uow:
            # the same order as the merge's own lock_users, so the two never deadlock;
            # an unlink or link on either account waits until the merge commits
            for user_id in sorted((user.id, ticket.other_user_id)):
                await self._user_repository.find_for_update(user_id)
            if await self._linker.owner_of(ticket.claim) != ticket.other_user_id:
                raise _invalid()
            return await self._merger.merge(user, ticket.other_user_id, client_ip)
