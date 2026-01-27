from dataclasses import dataclass
from typing import Any, Final, Optional, Self

from aiogram.types import ChatMemberUpdated
from aiogram.types import User as AiogramUser
from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models.hwid import HwidDeviceDto

from src.application.common import (
    Cryptographer,
    EventPublisher,
    Interactor,
    Notifier,
    Remnawave,
    TranslatorRunner,
)
from src.application.common.dao import PlanDao, SettingsDao, SubscriptionDao, UserDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import MessagePayloadDto, PlanDto, SubscriptionDto, UserDto
from src.application.events import UserRegisteredEvent
from src.core.config import AppConfig
from src.core.constants import REMNASHOP_PREFIX
from src.core.enums import Locale, PlanAvailability, Role
from src.core.exceptions import PermissionDeniedError, UserNotFoundError
from src.core.types import RemnaUserDto
from src.telegram.keyboards import get_contact_support_keyboard


@dataclass(frozen=True)
class GetAdminsResultDto:
    telegram_id: int
    name: str
    role: Role
    is_deletable: bool


class GetAdmins(Interactor[None, list[GetAdminsResultDto]]):
    required_permission = Permission.MANAGE_ADMINS

    def __init__(self, user_dao: UserDao) -> None:
        self._user_dao = user_dao

    async def _execute(self, actor: UserDto, data: None) -> list[GetAdminsResultDto]:
        target_roles = [Role.OWNER] + Role.OWNER.get_subordinates()
        admins = await self._user_dao.filter_by_role(role=target_roles)

        logger.info(f"{actor.log} Retrieved admins list for management")

        return [
            GetAdminsResultDto(
                telegram_id=admin.telegram_id,
                name=admin.name,
                role=admin.role,
                is_deletable=self._is_deletable(actor, admin),
            )
            for admin in admins
        ]

    def _is_deletable(self, actor: UserDto, target: UserDto) -> bool:
        return (
            target.telegram_id != actor.telegram_id
            and target.role != Role.OWNER
            and target.role > actor.role
        )


@dataclass(frozen=True)
class GetOrCreateUserDto:
    telegram_id: int
    username: Optional[str]
    full_name: str
    language_code: Optional[str]
    event_type: str

    @classmethod
    def from_aiogram(cls, user: AiogramUser, event_type: str) -> Self:
        return cls(
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name,
            language_code=user.language_code,
            event_type=event_type,
        )


class GetOrCreateUser(Interactor[GetOrCreateUserDto, Optional[UserDto]]):
    required_permission = None

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
        config: AppConfig,
        cryptographer: Cryptographer,
        event_publisher: EventPublisher,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao
        self.config = config
        self.cryptographer = cryptographer
        self.event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: GetOrCreateUserDto) -> Optional[UserDto]:
        async with self.uow:
            user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if user:
                return user

            if data.event_type == ChatMemberUpdated.__name__:
                logger.debug(
                    f"Skipping user creation for '{data.telegram_id}' "
                    f"due to '{ChatMemberUpdated.__name__}' event"
                )
                return None

            user_dto = self._create_user_dto(data)
            user = await self.user_dao.create(user_dto)
            await self.uow.commit()

        await self._publish_event(user)
        logger.info(f"New user '{user.telegram_id}' created")
        return user

    def _create_user_dto(self, data: GetOrCreateUserDto) -> UserDto:
        is_owner = data.telegram_id == self.config.bot.owner_id

        if data.language_code in self.config.locales:
            locale = Locale(data.language_code)
        else:
            locale = self.config.default_locale

        return UserDto(
            telegram_id=data.telegram_id,
            username=data.username,
            referral_code=self.cryptographer.generate_short_code(data.telegram_id),
            name=data.full_name,
            role=Role.OWNER if is_owner else Role.USER,
            language=locale,
        )

    async def _publish_event(self, user: UserDto) -> None:
        await self.event_publisher.publish(
            UserRegisteredEvent(
                telegram_id=user.telegram_id,
                username=user.username,
                name=user.name,
            )
        )


@dataclass(frozen=True)
class SetBotBlockedStatusDto:
    telegram_id: int
    is_blocked: bool


class SetBotBlockedStatus(Interactor[SetBotBlockedStatusDto, None]):
    required_permission = None

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: SetBotBlockedStatusDto) -> None:
        async with self.uow:
            await self.user_dao.set_bot_blocked_status(data.telegram_id, data.is_blocked)
            await self.uow.commit()

        logger.info(f"Set bot blocked status for user '{data.telegram_id}' to '{data.is_blocked}'")


class ToggleUserBlockedStatus(Interactor[int, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, user_dao: UserDao) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, telegram_id: int) -> None:
        async with self.uow:
            await self.user_dao.toggle_blocked_status(telegram_id)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled user '{telegram_id}' blocked status")


class RevokeRole(Interactor[int, None]):
    required_permission = Permission.REVOKE_ROLE

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, telegram_id: int) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(telegram_id)

            if not target_user:
                logger.warning(f"User '{telegram_id}' not found for role revocation")
                raise UserNotFoundError(telegram_id)

            if actor.telegram_id == target_user.telegram_id:
                logger.warning(f"User '{actor.telegram_id}' tried to revoke their own role")
                raise PermissionDeniedError

            if not actor.role > target_user.role:
                logger.warning(
                    f"User '{actor.telegram_id}' ({actor.role}) tried to revoke role "
                    f"from '{target_user.telegram_id}' ({target_user.role})"
                )
                raise PermissionDeniedError

            if target_user.role == Role.OWNER:
                logger.warning(f"Attempt to revoke role from OWNER '{telegram_id}' blocked")
                raise PermissionDeniedError

            target_user.role = Role.USER
            await self.user_dao.update(target_user)
            await self.uow.commit()

            logger.info(
                f"Role for user '{telegram_id}' revoked to '{Role.USER}' by '{actor.telegram_id}'"
            )


@dataclass(frozen=True)
class SetUserRoleDto:
    telegram_id: int
    role: Role


class SetUserRole(Interactor[SetUserRoleDto, None]):
    required_permission = Permission.ASSIGN_ROLE

    def __init__(self, uow: UnitOfWork, user_dao: UserDao):
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: SetUserRoleDto) -> None:
        target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)

        if not target_user:
            logger.warning(
                f"{actor.log} Attempted to change role for non-existent user '{data.telegram_id}'"
            )
            raise ValueError(f"User '{data.telegram_id}' not found")

        async with self.uow:
            target_user.role = data.role
            await self.user_dao.update(target_user)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Changed role for user '{data.telegram_id}' to '{data.role.value}'"
        )


@dataclass(frozen=True)
class SearchUsersDto:
    query: Optional[str] = None
    forward_from_id: Optional[int] = None
    is_forwarded_from_bot: bool = False


class SearchUsers(Interactor[SearchUsersDto, list[UserDto]]):
    required_permission = Permission.USER_SEARCH

    def __init__(self, user_dao: UserDao):
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: SearchUsersDto) -> list[UserDto]:
        found_users = []

        if data.forward_from_id and not data.is_forwarded_from_bot:
            telegram_id = data.forward_from_id
            user = await self.user_dao.get_by_telegram_id(telegram_id)
            if user:
                found_users.append(user)
                logger.info(f"Search by forwarded message, found user '{telegram_id}'")
            else:
                logger.warning(f"Search by forwarded message, user '{telegram_id}' not found")

        elif data.query:
            query = data.query.strip()

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


class UnblockAllUsers(Interactor[None, int]):
    required_permission = Permission.UNBLOCK_ALL

    def __init__(self, uow: UnitOfWork, user_dao: UserDao):
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: None) -> int:
        blocked_count = await self.user_dao.count_blocked()

        if blocked_count > 0:
            async with self.uow:
                await self.user_dao.unblock_all()
                await self.uow.commit()

            logger.warning(f"{actor.log} Unblocked all '{blocked_count}' users")
        else:
            logger.info(f"{actor.log} Attempted to unblock all, but blacklist is empty")

        return blocked_count


@dataclass(frozen=True)
class GetUserProfileResultDto:
    target_user: UserDto
    subscription: Optional[SubscriptionDto]
    show_points: bool
    is_not_self: bool
    can_edit: bool


class GetUserProfile(Interactor[int, GetUserProfileResultDto]):
    required_permission = Permission.USER_EDITOR

    def __init__(
        self,
        user_dao: UserDao,
        settings_dao: SettingsDao,
        subscription_dao: SubscriptionDao,
        config: AppConfig,
    ):
        self.user_dao = user_dao
        self.settings_dao = settings_dao
        self.subscription_dao = subscription_dao
        self.config = config

    async def _execute(self, actor: UserDto, telegram_id: int) -> GetUserProfileResultDto:
        target_user = await self.user_dao.get_by_telegram_id(telegram_id)

        if not target_user:
            raise ValueError(f"User '{telegram_id}' not found")

        settings = await self.settings_dao.get()
        subscription = await self.subscription_dao.get_current(telegram_id)

        logger.info(f"{actor.log} Viewed details for user '{telegram_id}'")

        return GetUserProfileResultDto(
            target_user=target_user,
            subscription=subscription,
            show_points=settings.referral.reward.is_points,
            is_not_self=target_user.telegram_id != actor.telegram_id,
            can_edit=actor.role > target_user.role,
        )


@dataclass(frozen=True)
class GetUserProfileSubscriptionResultDto:
    subscription: SubscriptionDto
    remna_user: RemnaUserDto
    last_node_name: Optional[str] = None

    @property
    def can_edit(self) -> bool:
        return not self.subscription.is_expired

    @property
    def formatted_internal_squads(self) -> str | bool:
        if not self.remna_user.active_internal_squads:
            return False
        return ", ".join(s.name for s in self.remna_user.active_internal_squads)

    @property
    def formatted_external_squad(self) -> str | bool:  # TODO: add name
        if not self.remna_user.external_squad_uuid:
            return False
        return str(self.remna_user.external_squad_uuid)


class GetUserProfileSubscription(Interactor[int, GetUserProfileSubscriptionResultDto]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
        remnawave_sdk: RemnawaveSDK,
    ):
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave
        self.remnawave_sdk = remnawave_sdk

    async def _execute(
        self,
        actor: UserDto,
        telegram_id: int,
    ) -> GetUserProfileSubscriptionResultDto:
        subscription = await self.subscription_dao.get_current(telegram_id)
        if not subscription:
            raise ValueError(f"Current subscription for user '{telegram_id}' not found")

        remna_user = await self.remnawave.get_user_by_uuid(subscription.user_remna_id)
        if not remna_user:
            raise ValueError(f"User Remnawave for '{telegram_id}' not found")

        last_node = None
        if remna_user.last_connected_node_uuid:
            try:
                last_node = await self.remnawave_sdk.nodes.get_one_node(
                    remna_user.last_connected_node_uuid
                )
            except Exception as e:
                logger.error(f"Failed to fetch node info: {e}")

        logger.info(f"{actor.log} Viewed subscription details for '{telegram_id}'")

        return GetUserProfileSubscriptionResultDto(
            subscription=subscription,
            remna_user=remna_user,
            last_node_name=last_node.name if last_node else None,
        )


@dataclass(frozen=True)
class GetUserDevicesResultDto:
    devices: list[HwidDeviceDto]
    current_count: int
    max_count: int
    subscription: SubscriptionDto


class GetUserDevices(Interactor[int, GetUserDevicesResultDto]):
    required_permission = Permission.USER_SUBSCRIPTION_EDITOR

    def __init__(
        self,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        remnawave: Remnawave,
    ):
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.remnawave = remnawave

    async def _execute(self, actor: UserDto, telegram_id: int) -> GetUserDevicesResultDto:
        target_user = await self.user_dao.get_by_telegram_id(telegram_id)
        if not target_user:
            raise ValueError(f"User '{telegram_id}' not found")

        subscription = await self.subscription_dao.get_current(telegram_id)
        if not subscription:
            raise ValueError(f"Subscription for '{telegram_id}' not found")

        devices = await self.remnawave.get_devices(subscription.user_remna_id)

        logger.info(f"{actor.log} Retrieved '{len(devices)}' devices for user '{telegram_id}'")

        return GetUserDevicesResultDto(
            devices=devices,
            current_count=len(devices),
            max_count=subscription.device_limit,
            subscription=subscription,
        )


class GetAvailablePlans(Interactor[UserDto, list[PlanDto]]):
    required_permission = None

    def __init__(self, user_dao: UserDao, plan_dao: PlanDao):
        self.user_dao = user_dao
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, data: UserDto) -> list[PlanDto]:
        all_active_plans = await self.plan_dao.get_active_plans()

        filtered_plans: list[PlanDto] = []

        has_any_subscription = await self.user_dao.has_any_subscription(data.telegram_id)
        is_invited_user = await self.user_dao.is_invited_user(data.telegram_id)

        for plan in all_active_plans:
            match plan.availability:
                case PlanAvailability.ALL:
                    filtered_plans.append(plan)

                case PlanAvailability.NEW if has_any_subscription:
                    logger.info(f"{data.log} Eligible for new user plan '{plan.name}'")
                    filtered_plans.append(plan)

                case PlanAvailability.EXISTING if has_any_subscription:
                    logger.info(f"{data.log} Eligible for existing user plan '{plan.name}'")
                    filtered_plans.append(plan)

                case PlanAvailability.INVITED if is_invited_user:
                    logger.info(f"{data.log} Eligible for invited user plan '{plan.name}'")
                    filtered_plans.append(plan)

                case PlanAvailability.ALLOWED if data.telegram_id in plan.allowed_user_ids:
                    logger.info(f"{data.log} Explicitly allowed for plan '{plan.name}'")
                    filtered_plans.append(plan)

        logger.info(
            f"{data.log} Filtered '{len(filtered_plans)}' available plans "
            f"out of '{len(all_active_plans)}' active"
        )
        return filtered_plans


@dataclass(frozen=True)
class SetUserPersonalDiscountDto:
    telegram_id: int
    discount: int


class SetUserPersonalDiscount(Interactor[SetUserPersonalDiscountDto, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, user_dao: UserDao):
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: SetUserPersonalDiscountDto) -> None:
        if not (0 <= data.discount <= 100):
            raise ValueError(f"Invalid discount value '{data.discount}'")

        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if not target_user:
                raise ValueError(f"User '{data.telegram_id}' not found")

            target_user.personal_discount = data.discount
            await self.user_dao.update(target_user)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Set personal discount to '{data.discount}' for user '{data.telegram_id}'"
        )


@dataclass(frozen=True)
class ChangeUserPointsDto:
    telegram_id: int
    amount: int


class ChangeUserPoints(Interactor[ChangeUserPointsDto, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, user_dao: UserDao):
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: ChangeUserPointsDto) -> None:
        async with self.uow:
            target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
            if not target_user:
                logger.error(f"{actor.log} User not found with id '{data.telegram_id}'")
                raise ValueError(f"User '{data.telegram_id}' not found")

            new_points = target_user.points + data.amount
            if new_points < 0:
                raise ValueError(
                    f"{actor.log} Points balance cannot be negative for '{data.telegram_id}'"
                )

            target_user.points = new_points
            await self.user_dao.update(target_user)
            await self.uow.commit()

        operation = "Added" if data.amount > 0 else "Subtracted"
        logger.info(f"{actor.log} {operation} '{abs(data.amount)}' points for '{data.telegram_id}'")


@dataclass(frozen=True)
class SendMessageToUserDto:
    telegram_id: int
    payload: dict[str, Any]


class SendMessageToUser(Interactor[SendMessageToUserDto, bool]):
    required_permission = Permission.USER_EDITOR

    def __init__(
        self,
        user_dao: UserDao,
        notifier: Notifier,
        config: AppConfig,
        i18n: TranslatorRunner,
    ):
        self.user_dao = user_dao
        self.notifier = notifier
        self.config = config
        self.i18n = i18n

    async def _execute(self, actor: UserDto, data: SendMessageToUserDto) -> bool:
        target_user = await self.user_dao.get_by_telegram_id(data.telegram_id)
        if not target_user:
            raise ValueError(f"User '{data.telegram_id}' not found")

        support_text = self.i18n.get("contact-support-help")
        support_username = self.config.bot.support_username.get_secret_value()

        payload = data.payload.copy()
        payload["reply_markup"] = get_contact_support_keyboard(support_username, support_text)

        message = await self.notifier.notify_user(
            user=target_user,
            payload=MessagePayloadDto(**payload),
        )

        if message:
            logger.info(f"{actor.log} Sent message to user '{data.telegram_id}'")
            return True

        logger.warning(f"{actor.log} Failed to send message to user '{data.telegram_id}'")
        return False


USER_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    GetAdmins,
    GetOrCreateUser,
    SetBotBlockedStatus,
    ToggleUserBlockedStatus,
    RevokeRole,
    SetUserRole,
    SearchUsers,
    UnblockAllUsers,
    GetUserProfile,
    GetUserProfileSubscription,
    GetUserDevices,
    GetAvailablePlans,
    SetUserPersonalDiscount,
    ChangeUserPoints,
    SendMessageToUser,
)
