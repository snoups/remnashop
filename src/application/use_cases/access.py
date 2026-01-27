from dataclasses import dataclass
from typing import Final, Optional, Union

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from loguru import logger

from src.application.common import EventPublisher, Interactor, Notifier
from src.application.common.dao import SettingsDao, UserDao, WaitlistDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import SettingsDto, TempUserDto, UserDto
from src.application.events import ErrorEvent
from src.core.config import AppConfig
from src.core.enums import AccessMode

ALLOWED_STATUSES: Final[tuple[ChatMemberStatus, ...]] = (
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
)


@dataclass(frozen=True)
class CheckAccessDto:
    temp_user: TempUserDto
    is_payment_event: bool
    is_referral_event: bool

    @property
    def telegram_id(self) -> int:
        return self.temp_user.telegram_id


class CheckAccess(Interactor[CheckAccessDto, bool]):
    required_permission = None

    def __init__(
        self,
        user_dao: UserDao,
        settings_dao: SettingsDao,
        waitlist_dao: WaitlistDao,
        notifier: Notifier,
    ) -> None:
        self.user_dao = user_dao
        self.settings_dao = settings_dao
        self.waitlist_dao = waitlist_dao
        self.notifier = notifier

    async def _execute(self, actor: UserDto, data: CheckAccessDto) -> bool:
        user = await self.user_dao.get_by_telegram_id(data.telegram_id)
        settings = await self.settings_dao.get()

        if user:
            if user.is_blocked:
                logger.info(f"Access denied for user '{data.telegram_id}' because they are blocked")
                return False

            if user.is_privileged:
                logger.info(f"Access allowed for privileged user '{data.telegram_id}'")
                return True

        if settings.access.mode == AccessMode.RESTRICTED:
            await self.notifier.notify_user(data.temp_user, i18n_key="ntf-access.maintenance")
            logger.info(f"Access denied for user '{data.telegram_id}' due to restricted mode")
            return False

        if user:
            if data.is_payment_event and not settings.access.payments_allowed:
                await self.notifier.notify_user(
                    user=data.temp_user, i18n_key="ntf-access.payments-disabled"
                )
                logger.info(
                    f"Access denied for payment event for user '{data.telegram_id}' "
                    f"because payments are disabled"
                )
                return await self._manage_waitlist(data.telegram_id)
            return True

        return await self._process_new_user(data, settings)

    async def _process_new_user(self, data: CheckAccessDto, settings: SettingsDto) -> bool:
        if not settings.access.registration_allowed:
            await self.notifier.notify_user(
                user=data.temp_user,
                i18n_key="ntf-access.registration-disabled",
            )
            logger.info(f"Registration is globally disabled for user '{data.telegram_id}'")
            return False

        if settings.access.mode == AccessMode.INVITED:
            if data.is_referral_event:
                logger.info(f"Access allowed for referral event for user '{data.telegram_id}'")
                return True

            await self.notifier.notify_user(
                user=data.temp_user,
                i18n_key="ntf-access.registration-invite-only",
            )
            logger.info(f"Access denied for user '{data.telegram_id}' because not a referral")
            return False

        logger.info(f"New user '{data.telegram_id}' allowed to register")
        return True

    async def _manage_waitlist(self, telegram_id: int) -> bool:
        if not await self.waitlist_dao.exists(telegram_id):
            await self.waitlist_dao.add(telegram_id)
            logger.info(f"User '{telegram_id}' added to payment waitlist")
        return False


class AcceptRules(Interactor[None, None]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        uow: UnitOfWork,
        user_dao: UserDao,
    ) -> None:
        self.uow = uow
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self.uow:
            actor.is_rules_accepted = True
            await self.user_dao.update(actor)
            await self.uow.commit()

        logger.info(f"{actor.log} Accepted rules")


@dataclass(frozen=True)
class CheckRulesResultDto:
    is_required: bool
    is_accepted: bool
    rules_link: Optional[str] = None


class CheckRules(Interactor[None, CheckRulesResultDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, settings_dao: SettingsDao) -> None:
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: None) -> CheckRulesResultDto:
        settings = await self.settings_dao.get()

        if actor.is_privileged:
            logger.debug(f"User '{actor.telegram_id}' skipped rules check due to privileges")
            return CheckRulesResultDto(is_required=False, is_accepted=True)

        if not settings.requirements.rules_required:
            logger.debug(f"Rules check skipped for '{actor.telegram_id}': requirement is disabled")
            return CheckRulesResultDto(is_required=False, is_accepted=True)

        rules_link = settings.requirements.rules_link.get_secret_value()

        if actor.is_rules_accepted:
            logger.debug(f"User '{actor.telegram_id}' has already accepted rules")
            return CheckRulesResultDto(is_required=True, is_accepted=True, rules_link=rules_link)

        logger.debug(f"User '{actor.telegram_id}' must accept rules before proceeding")
        return CheckRulesResultDto(is_required=True, is_accepted=False, rules_link=rules_link)


@dataclass(frozen=True)
class CheckChannelSubscriptionResultDto:
    is_subscribed: bool
    status: Optional[ChatMemberStatus] = None
    channel_url: Optional[str] = None
    error_occurred: bool = False


class CheckChannelSubscription(Interactor[None, CheckChannelSubscriptionResultDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        settings_dao: SettingsDao,
        bot: Bot,
        config: AppConfig,
        event_publisher: EventPublisher,
    ) -> None:
        self.settings_dao = settings_dao
        self.bot = bot
        self.config = config
        self.event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: None) -> CheckChannelSubscriptionResultDto:
        settings = await self.settings_dao.get()

        if not settings.requirements.channel_required:
            logger.debug("Channel check skipped: requirement is disabled in settings")
            return CheckChannelSubscriptionResultDto(is_subscribed=True)

        if actor.is_privileged:
            logger.debug(f"User '{actor.telegram_id}' skipped channel check due to privileges")
            return CheckChannelSubscriptionResultDto(is_subscribed=True)

        req = settings.requirements
        channel_link = req.channel_link.get_secret_value()
        channel_url = req.channel_url

        chat_id: Union[str, int, None] = None
        if req.channel_has_username:
            chat_id = channel_link
        elif req.channel_id:
            chat_id = req.channel_id

        if chat_id is None:
            logger.warning(
                f"Channel check skipped for '{actor.telegram_id}': no valid chat_id or username"
            )
            return CheckChannelSubscriptionResultDto(is_subscribed=True)

        try:
            member = await self.bot.get_chat_member(chat_id=chat_id, user_id=actor.telegram_id)

            is_subscribed = member.status in ALLOWED_STATUSES
            return CheckChannelSubscriptionResultDto(is_subscribed, member.status, channel_url)

        except Exception as e:
            logger.error(f"Failed to check channel for '{actor.telegram_id}': '{e}'")

            error_event = ErrorEvent(
                **self.config.build.data,
                #
                telegram_id=actor.telegram_id,
                username=actor.username,
                name=actor.name,
                #
                exception=e,
            )

            await self.event_publisher.publish(error_event)
            return CheckChannelSubscriptionResultDto(is_subscribed=True, error_occurred=True)


ACCESS_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    CheckAccess,
    AcceptRules,
    CheckRules,
    CheckChannelSubscription,
)
