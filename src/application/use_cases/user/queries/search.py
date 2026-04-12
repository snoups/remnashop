from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import TransactionDao, UserDao
from src.application.common.policy import Permission
from src.application.dto import TransactionDto, UserDto
from src.core.constants import REMNASHOP_PREFIX


@dataclass(frozen=True)
class SearchUsersDto:
    query: Optional[str] = None
    forward_from_id: Optional[int] = None
    forward_sender_name: Optional[str] = None
    is_forwarded_from_bot: bool = False


@dataclass(frozen=True)
class SmartSearchResult:
    users: list[UserDto] = field(default_factory=list)
    transaction: Optional[TransactionDto] = None
    transaction_searched: bool = False

    @property
    def found_transaction(self) -> bool:
        return self.transaction is not None

    @property
    def found_users(self) -> bool:
        return bool(self.users)


class SearchUsers(Interactor[SearchUsersDto, list[UserDto]]):
    required_permission = Permission.USER_SEARCH

    def __init__(self, user_dao: UserDao) -> None:
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: SearchUsersDto) -> list[UserDto]:  # noqa: C901
        found_users: list[UserDto] = []

        if (data.forward_from_id or data.forward_sender_name) and not data.is_forwarded_from_bot:
            if data.forward_from_id:
                user = await self.user_dao.get_by_telegram_id(data.forward_from_id)
                if user:
                    found_users.append(user)
                    logger.info(f"Search by forwarded message, found user '{data.forward_from_id}'")
                    return found_users

                logger.warning(
                    f"Search by forwarded message, user '{data.forward_from_id}' not found"
                )

            if data.forward_sender_name:
                sender_name = data.forward_sender_name.strip()
                users = await self.user_dao.get_by_partial_name(sender_name)
                found_users.extend(users)
                logger.info(f"Search by forwarded name '{sender_name}', found '{len(users)}' users")

            return found_users

        if data.query:
            query = data.query.strip().removeprefix("@")

            if query.isdigit():
                telegram_id = int(query)
                user = await self.user_dao.get_by_telegram_id(telegram_id)
                if user:
                    found_users.append(user)
                    logger.info(f"Searched by Telegram ID '{telegram_id}', user found")
                else:
                    logger.warning(f"Searched by Telegram ID '{telegram_id}', user not found")

            elif query.startswith(REMNASHOP_PREFIX):
                try:
                    telegram_id = int(query.split("_", maxsplit=1)[1])
                    user = await self.user_dao.get_by_telegram_id(telegram_id)
                    if user:
                        found_users.append(user)
                        logger.info(f"Searched by Remnashop ID '{telegram_id}', user found")
                    else:
                        logger.warning(f"Searched by Remnashop ID '{telegram_id}', user not found")
                except (IndexError, ValueError):
                    logger.warning(f"Failed to parse Remnashop ID from query '{query}'")

            else:
                found_users = await self.user_dao.get_by_partial_name(query)
                logger.info(
                    f"Searched users by partial name '{query}', found '{len(found_users)}' users"
                )

        return found_users


class SmartSearch(Interactor[SearchUsersDto, SmartSearchResult]):
    required_permission = Permission.USER_SEARCH

    def __init__(self, search_users: SearchUsers, transaction_dao: TransactionDao) -> None:
        self.search_users = search_users
        self.transaction_dao = transaction_dao

    async def _execute(self, actor: UserDto, data: SearchUsersDto) -> SmartSearchResult:
        if data.query:
            try:
                payment_id = UUID(data.query.strip())
                transaction = await self.transaction_dao.get_by_payment_id(payment_id)
                if transaction:
                    logger.info(f"Smart search: found transaction '{payment_id}'")
                    return SmartSearchResult(transaction=transaction, transaction_searched=True)
                logger.warning(f"Smart search: transaction '{payment_id}' not found")
                return SmartSearchResult(transaction_searched=True)
            except ValueError:
                pass

        found_users = await self.search_users(actor, data)
        return SmartSearchResult(users=found_users)
