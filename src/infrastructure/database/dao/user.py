from typing import Optional, cast

from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import Integer, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.dao import UserDao
from src.application.dto import UserDto
from src.core.constants import TTL_1H, TTL_6H
from src.core.enums import Role, SubscriptionStatus
from src.infrastructure.database.models import Referral, Subscription, Transaction, User
from src.infrastructure.redis.cache import invalidate_cache, provide_cache
from src.infrastructure.redis.keys import (
    USER_COUNT_PREFIX,
    USER_LIST_PREFIX,
    RoleKey,
    UserCacheKey,
)


class UserDaoImpl(UserDao):
    def __init__(
        self,
        session: AsyncSession,
        retort: Retort,
        conversion_retort: ConversionRetort,
        redis: Redis,
    ) -> None:
        self.session = session
        self.retort = retort
        self.conversion_retort = conversion_retort
        self.redis = redis

        self._convert_to_dto = self.conversion_retort.get_converter(User, UserDto)
        self._convert_to_dto_list = self.conversion_retort.get_converter(list[User], list[UserDto])

    # @invalidate_cache(key_builder=[USER_COUNT_PREFIX, USER_LIST_PREFIX])
    # @invalidate_cache(key_builder=UserCacheKey)
    async def create(self, user: UserDto) -> UserDto:
        user_data = self.retort.dump(user)
        db_user = User(**user_data)

        self.session.add(db_user)
        await self.session.flush()

        logger.debug(f"New user '{user.telegram_id}' created in database")
        return self._convert_to_dto(db_user)

    # @provide_cache(ttl=TTL_1H, key_builder=UserCacheKey)
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserDto]:
        stmt = select(User).where(User.telegram_id == telegram_id)
        db_user = await self.session.scalar(stmt)

        if db_user:
            logger.debug(f"User '{telegram_id}' found in database")
            return self._convert_to_dto(db_user)

        logger.debug(f"User '{telegram_id}' not found")
        return None

    async def get_by_telegram_ids(self, telegram_ids: list[int]) -> list[UserDto]:
        if not telegram_ids:
            return []

        stmt = select(User).where(User.telegram_id.in_(telegram_ids))
        result = await self.session.scalars(stmt)
        db_users = cast(list, result.all())

        logger.debug(f"Retrieved '{len(db_users)}' users by telegram ID list")
        return self._convert_to_dto_list(db_users)

    async def get_by_partial_name(self, query_name: str) -> list[UserDto]:
        search_pattern = f"%{query_name}%"
        stmt = select(User).where(
            or_(
                User.name.ilike(search_pattern),
                User.username.ilike(search_pattern),
            )
        )
        result = await self.session.scalars(stmt)
        db_users = cast(list, result.all())

        logger.debug(f"Found '{len(db_users)}' users matching query '{query_name}'")
        return self._convert_to_dto_list(db_users)

    async def get_by_referral_code(self, referral_code: str) -> Optional[UserDto]:
        stmt = select(User).where(User.referral_code == referral_code)
        db_user = await self.session.scalar(stmt)

        if db_user:
            logger.debug(f"User with referral code '{referral_code}' found")
            return self._convert_to_dto(db_user)

        logger.debug(f"User with referral code '{referral_code}' not found")
        return None

    # @provide_cache(prefix=USER_LIST_PREFIX, ttl=TTL_1H)
    async def get_all(self, limit: int = 100, offset: int = 0) -> list[UserDto]:
        stmt = select(User).limit(limit).offset(offset)
        result = await self.session.scalars(stmt)
        db_users = cast(list, result.all())

        logger.debug(
            f"Retrieved '{len(db_users)}' users from database "
            f"with limit '{limit}' and offset '{offset}'"
        )
        return self._convert_to_dto_list(db_users)

    # @invalidate_cache(key_builder=[USER_COUNT_PREFIX, USER_LIST_PREFIX])
    # @invalidate_cache(key_builder=UserCacheKey)
    async def update(self, user: UserDto) -> Optional[UserDto]:
        if not user.changed_data:
            logger.debug(f"No changes detected for user '{user.telegram_id}', skipping update")
            return await self.get_by_telegram_id(user.telegram_id)

        stmt = (
            update(User)
            .where(User.telegram_id == user.telegram_id)
            .values(**user.changed_data)
            .returning(User)
        )
        db_user = await self.session.scalar(stmt)

        if db_user:
            logger.debug(
                f"User '{user.telegram_id}' updated successfully with data '{user.changed_data}'"
            )
            return self._convert_to_dto(db_user)

        logger.warning(f"Failed to update user '{user.telegram_id}'")
        return None

    # @invalidate_cache(key_builder=[USER_COUNT_PREFIX, USER_LIST_PREFIX])
    # @invalidate_cache(key_builder=UserCacheKey)
    async def delete(self, telegram_id: int) -> bool:
        stmt = delete(User).where(User.telegram_id == telegram_id).returning(User.id)
        result = await self.session.execute(stmt)
        deleted_id = result.scalar_one_or_none()

        if deleted_id:
            logger.debug(f"User '{telegram_id}' deleted from database")
            return True

        logger.debug(f"User '{telegram_id}' not found for deletion")
        return False

    async def exists(self, telegram_id: int) -> bool:
        stmt = select(select(User).where(User.telegram_id == telegram_id).exists())
        is_exists = await self.session.scalar(stmt) or False

        logger.debug(f"User '{telegram_id}' existence status is '{is_exists}'")
        return is_exists

    # @provide_cache(prefix=USER_COUNT_PREFIX, ttl=TTL_6H)
    async def count(self) -> int:
        stmt = select(func.count()).select_from(User)
        total = await self.session.scalar(stmt) or 0

        logger.debug(f"Total users count requested: '{total}'")
        return total

    # @provide_cache(ttl=TTL_1H, key_builder=RoleKey)
    async def filter_by_role(self, role: list[Role]) -> list[UserDto]:
        stmt = select(User)

        if isinstance(role, list):
            stmt = stmt.where(User.role.in_(role))
        else:
            stmt = stmt.where(User.role == role)

        result = await self.session.scalars(stmt)
        db_users = cast(list, result.all())

        logger.debug(f"Filtered '{len(db_users)}' users with role '{role}'")
        return self._convert_to_dto_list(db_users)

    # @invalidate_cache(key_builder=[USER_COUNT_PREFIX, USER_LIST_PREFIX])
    # @invalidate_cache(key_builder=UserCacheKey)
    async def set_trial_available(self, telegram_id: int, is_trial_available: bool) -> None:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_trial_available=is_trial_available)
        )
        await self.session.execute(stmt)
        logger.debug(
            f"Trial available status for user '{telegram_id}' set to '{is_trial_available}'"
        )

    # @invalidate_cache(key_builder=[USER_COUNT_PREFIX, USER_LIST_PREFIX])
    # @invalidate_cache(key_builder=UserCacheKey)
    async def set_bot_blocked_status(self, telegram_id: int, is_bot_blocked: bool) -> None:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_bot_blocked=is_bot_blocked)
        )
        await self.session.execute(stmt)
        logger.debug(f"Bot blocked status for user '{telegram_id}' set to '{is_bot_blocked}'")

    async def set_current_subscription(self, telegram_id: int, subscription_id: int) -> None:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(current_subscription_id=subscription_id)
        )
        await self.session.execute(stmt)
        logger.debug(f"Current subscription for user '{telegram_id}' set to '{subscription_id}'")

    # @invalidate_cache(key_builder=[USER_COUNT_PREFIX, USER_LIST_PREFIX])
    # @invalidate_cache(key_builder=UserCacheKey)
    async def clear_current_subscription(self, telegram_id: int) -> None:
        stmt = (
            update(User).where(User.telegram_id == telegram_id).values(current_subscription_id=None)
        )
        await self.session.execute(stmt)
        logger.debug(f"Current subscription cleared for user '{telegram_id}'")

    async def get_blocked_users(self) -> list[UserDto]:
        stmt = select(User).where(User.is_blocked.is_(True)).order_by(User.id.desc())

        result = await self.session.execute(stmt)
        db_users = result.scalars().all()

        logger.debug(f"Retrieved '{len(db_users)}' blocked users")
        return self._convert_to_dto_list(list(db_users))

    async def get_recent_activity_users(
        self,
        excluded_ids: Optional[list[int]] = None,
    ) -> list[UserDto]:
        stmt = select(User)

        if excluded_ids:
            stmt = stmt.where(User.telegram_id.not_in(excluded_ids))

        stmt = stmt.order_by(User.updated_at.desc().nulls_last()).limit(10)
        result = await self.session.execute(stmt)
        db_users = result.scalars().all()

        logger.debug(f"Retrieved '{len(db_users)}' users with recent activity")
        return self._convert_to_dto_list(list(db_users))

    async def get_recent_registered_users(self, limit: int = 5) -> list[UserDto]:
        stmt = select(User).order_by(User.created_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        db_users = result.scalars().all()

        logger.debug(f"Retrieved '{len(db_users)}' recently registered users")
        return self._convert_to_dto_list(list(db_users))

    async def unblock_all(self) -> None:
        stmt = update(User).where(User.is_blocked.is_(True)).values(is_blocked=False)
        await self.session.execute(stmt)
        logger.debug("All users unblocked")

    async def count_blocked(self) -> int:
        stmt = select(func.count()).select_from(User).where(User.is_blocked.is_(True))
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        logger.debug(f"Retrieved '{count}' blocked users")
        return count

    async def has_any_subscription(self, telegram_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.user_telegram_id == telegram_id)
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        logger.debug(
            f"Checked subscription status for user '{telegram_id}', found '{count}' active"
        )
        return count > 0

    async def is_invited_user(self, telegram_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(Referral)
            .where(Referral.referred_telegram_id == telegram_id)
        )

        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        is_invited = count > 0
        logger.debug(f"Checked invite status for user '{telegram_id}', result '{is_invited}'")
        return is_invited

    async def toggle_blocked_status(self, telegram_id: int) -> None:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_blocked=~User.is_blocked)
            .returning(User.is_blocked)
        )

        result = await self.session.execute(stmt)
        new_status = result.scalar()

        logger.debug(
            f"Toggled blocked status for user '{telegram_id}', new status is '{new_status}'"
        )

    async def count_active_non_blocked(self) -> int:
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.is_blocked.is_(False), User.is_bot_blocked.is_(False))
        )
        count = await self.session.scalar(stmt) or 0
        logger.debug(f"Total active non-blocked users count is '{count}'")
        return count

    async def count_with_active_subscription(self) -> int:
        stmt = (
            select(func.count(User.id))
            .join(Subscription, User.current_subscription_id == Subscription.id)
            .where(
                User.is_blocked.is_(False),
                User.is_bot_blocked.is_(False),
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        count = await self.session.scalar(stmt) or 0
        logger.debug(f"Total users with active subscription count is '{count}'")
        return count

    async def count_with_expired_subscription(self) -> int:
        stmt = (
            select(func.count(User.id))
            .join(Subscription, User.current_subscription_id == Subscription.id)
            .where(
                User.is_blocked.is_(False),
                User.is_bot_blocked.is_(False),
                Subscription.status == SubscriptionStatus.EXPIRED,
            )
        )
        count = await self.session.scalar(stmt) or 0
        logger.debug(f"Total users with expired subscription count is '{count}'")
        return count

    async def count_with_trial_subscription(self) -> int:
        stmt = (
            select(func.count(User.id))
            .join(Subscription, User.current_subscription_id == Subscription.id)
            .where(
                User.is_blocked.is_(False),
                User.is_bot_blocked.is_(False),
                Subscription.is_trial.is_(True),
            )
        )
        count = await self.session.scalar(stmt) or 0
        logger.debug(f"Total users with trial subscription count is '{count}'")
        return count

    async def count_without_subscription(self) -> int:
        stmt = select(func.count(User.id)).where(
            User.is_blocked.is_(False),
            User.is_bot_blocked.is_(False),
            User.current_subscription_id.is_(None),
        )
        count = await self.session.scalar(stmt) or 0
        logger.debug(f"Total users without subscription count is '{count}'")
        return count

    async def get_active_non_blocked(self) -> list[UserDto]:
        stmt = select(User).where(User.is_blocked.is_(False), User.is_bot_blocked.is_(False))
        result = await self.session.scalars(stmt)
        db_users = cast(list, result.all())
        logger.debug(f"Retrieved '{len(db_users)}' active non-blocked users")
        return self._convert_to_dto_list(db_users)

    async def get_without_subscription(self) -> list[UserDto]:
        stmt = select(User).where(
            User.is_blocked.is_(False),
            User.is_bot_blocked.is_(False),
            User.current_subscription_id.is_(None),
        )
        result = await self.session.execute(stmt)
        return self._convert_to_dto_list(list(result.scalars()))

    async def get_with_expired_subscription(self) -> list[UserDto]:
        stmt = (
            select(User)
            .join(Subscription, User.current_subscription_id == Subscription.id)
            .where(
                User.is_blocked.is_(False),
                User.is_bot_blocked.is_(False),
                Subscription.status == SubscriptionStatus.EXPIRED,
            )
        )
        result = await self.session.execute(stmt)
        return self._convert_to_dto_list(list(result.scalars()))

    async def get_with_trial_subscription(self) -> list[UserDto]:
        stmt = (
            select(User)
            .join(Subscription, User.current_subscription_id == Subscription.id)
            .where(
                User.is_blocked.is_(False),
                User.is_bot_blocked.is_(False),
                Subscription.is_trial.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return self._convert_to_dto_list(list(result.scalars()))

    async def get_active_by_plan(self, plan_id: int) -> list[UserDto]:
        stmt = (
            select(User)
            .join(Subscription, User.current_subscription_id == Subscription.id)
            .where(
                User.is_blocked.is_(False),
                User.is_bot_blocked.is_(False),
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.plan_snapshot["id"].as_integer() == plan_id,
            )
        )
        result = await self.session.execute(stmt)
        db_users = list(result.scalars().all())

        logger.debug(f"Retrieved '{len(db_users)}' active users for plan_id '{plan_id}'")
        return self._convert_to_dto_list(db_users)
