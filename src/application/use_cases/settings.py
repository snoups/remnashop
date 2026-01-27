from typing import Final

from loguru import logger
from pydantic import SecretStr

from src.application.common import Interactor, Notifier
from src.application.common.dao import SettingsDao, WaitlistDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import SettingsDto, UserDto
from src.core.constants import T_ME
from src.core.enums import (
    AccessMode,
    AccessRequirements,
    ReferralAccrualStrategy,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
)
from src.core.types import NotificationType
from src.core.utils.validators import is_valid_url, is_valid_username
from src.infrastructure.taskiq.tasks.notifications import notify_payments_restored


class ChangeAccessMode(Interactor[AccessMode, None]):
    required_permission = Permission.SETTINGS_ACCESS

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, new_mode: AccessMode) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            old_mode = settings.access.mode
            settings.access.mode = new_mode
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Changed access mode from '{old_mode}' to '{new_mode}'")


class ToggleNotification(Interactor[NotificationType, SettingsDto]):
    required_permission = Permission.SETTINGS_NOTIFICATIONS

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, notification_type: NotificationType) -> SettingsDto:
        async with self.uow:
            settings = await self.settings_dao.get()
            settings.notifications.toggle(notification_type)
            updated = await self.settings_dao.update(settings)

            await self.uow.commit()

        logger.info(f"{actor.log} Toggled notification '{notification_type}'")
        return updated


class TogglePayments(Interactor[None, None]):
    required_permission = Permission.SETTINGS_ACCESS

    def __init__(
        self,
        uow: UnitOfWork,
        settings_dao: SettingsDao,
        waitlist_dao: WaitlistDao,
    ) -> None:
        self.uow = uow
        self.settings_dao = settings_dao
        self.waitlist_dao = waitlist_dao

    async def _execute(self, actor: UserDto, data: None) -> None:
        settings = await self.settings_dao.get()
        new_state = not settings.access.payments_allowed
        settings.access.payments_allowed = new_state

        async with self.uow:
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled payments availability to '{new_state}'")

        if new_state is True:
            waiting_users = await self.waitlist_dao.get_members()

            if waiting_users:
                logger.info(f"Triggering notification task for '{len(waiting_users)}' users")
                await notify_payments_restored.kiq(waiting_users)  # type: ignore[call-overload]

                await self.waitlist_dao.clear()
                logger.info("Waitlist has been cleared after triggering notifications")


class ToggleRegistration(Interactor[None, None]):
    required_permission = Permission.SETTINGS_ACCESS

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: None) -> None:
        settings = await self.settings_dao.get()
        new_state = not settings.access.registration_allowed
        settings.access.registration_allowed = new_state

        async with self.uow:
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled registration availability to '{new_state}'")


class ToggleConditionRequirement(Interactor[AccessRequirements, None]):
    required_permission = Permission.SETTINGS_REQUIREMENT

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, condition_type: AccessRequirements) -> None:
        settings = await self.settings_dao.get()

        if condition_type == AccessRequirements.RULES:
            settings.requirements.rules_required = not settings.requirements.rules_required
            new_state = settings.requirements.rules_required
        elif condition_type == AccessRequirements.CHANNEL:
            settings.requirements.channel_required = not settings.requirements.channel_required
            new_state = settings.requirements.channel_required
        else:
            logger.error(f"{actor.log} Tried to toggle unknown condition '{condition_type}'")
            return

        async with self.uow:
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled access requirement '{condition_type}' to '{new_state}'")


class UpdateRulesRequirement(Interactor[str, bool]):
    required_permission = Permission.SETTINGS_REQUIREMENT

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao, notifier: Notifier) -> None:
        self.uow = uow
        self.settings_dao = settings_dao
        self.notifier = notifier

    async def _execute(self, actor: UserDto, input_text: str) -> bool:
        input_text = input_text.strip()

        if not is_valid_url(input_text):
            logger.warning(f"{actor.log} Provided invalid rules link format: '{input_text}'")
            await self.notifier.notify_user(actor, i18n_key="ntf-common.invalid-value")
            return False

        settings = await self.settings_dao.get()
        settings.requirements.rules_link = SecretStr(input_text)

        async with self.uow:
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Successfully updated rules link")
        await self.notifier.notify_user(actor, i18n_key="ntf-common.value-updated")
        return True


class UpdateChannelRequirement(Interactor[str, None]):
    required_permission = Permission.SETTINGS_REQUIREMENT

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao, notifier: Notifier) -> None:
        self.uow = uow
        self.settings_dao = settings_dao
        self.notifier = notifier

    async def _execute(self, actor: UserDto, input_text: str) -> None:
        input_text = input_text.strip()
        settings = await self.settings_dao.get()

        if input_text.isdigit() or (input_text.startswith("-") and input_text[1:].isdigit()):
            await self._handle_id_input(input_text, settings)
            await self.notifier.notify_user(actor, i18n_key="ntf-common.value-updated")
        elif is_valid_username(input_text) or input_text.startswith(T_ME):
            settings.requirements.channel_link = SecretStr(input_text)
            await self.notifier.notify_user(actor, i18n_key="ntf-common.value-updated")

        else:
            logger.warning(f"{actor.log} Provided invalid channel format: '{input_text}'")
            await self.notifier.notify_user(actor, i18n_key="ntf-common.invalid-value")

        async with self.uow:
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Updated channel requirement")

    async def _handle_id_input(self, text: str, settings: SettingsDto) -> None:
        channel_id = int(text)
        if not text.startswith("-100") and not text.startswith("-"):
            channel_id = int(f"-100{text}")

        settings.requirements.channel_id = channel_id


class ToggleReferralSystem(Interactor[None, bool]):
    required_permission = Permission.SETTINGS_REFERRAL

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: None) -> bool:
        async with self.uow:
            settings = await self.settings_dao.get()
            old_status = settings.referral.enable
            settings.referral.enable = not old_status
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Toggled referral system "
            f"from '{old_status}' to '{settings.referral.enable}'"
        )
        return settings.referral.enable


class UpdateReferralLevel(Interactor[int, None]):
    required_permission = Permission.SETTINGS_REFERRAL

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, new_level: int) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            old_level = settings.referral.level.value
            settings.referral.level = ReferralLevel(new_level)

            current_config = settings.referral.reward.config
            new_config = {lvl: val for lvl, val in current_config.items() if lvl.value <= new_level}

            for level_enum in ReferralLevel:
                if level_enum.value <= new_level and level_enum not in new_config:
                    prev_val = new_config.get(ReferralLevel(level_enum.value - 1), 0)
                    new_config[level_enum] = prev_val

            settings.referral.reward.config = new_config
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Updated referral level from '{old_level}' to '{new_level}'")


class UpdateReferralRewardType(Interactor[ReferralRewardType, None]):
    required_permission = Permission.SETTINGS_REFERRAL

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, new_reward_type: ReferralRewardType) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            old_type = settings.referral.reward.type
            settings.referral.reward.type = new_reward_type
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Updated referral reward type from '{old_type}' to '{new_reward_type}'"
        )


class UpdateReferralAccrualStrategy(Interactor[ReferralAccrualStrategy, None]):
    required_permission = Permission.SETTINGS_REFERRAL

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, new_strategy: ReferralAccrualStrategy) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            old_strategy = settings.referral.accrual_strategy
            settings.referral.accrual_strategy = new_strategy
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Updated referral accrual strategy "
            f"from '{old_strategy}' to '{new_strategy}'"
        )


class UpdateReferralRewardStrategy(Interactor[ReferralRewardStrategy, None]):
    required_permission = Permission.SETTINGS_REFERRAL

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, new_strategy: ReferralRewardStrategy) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            old_strategy = settings.referral.reward.strategy
            settings.referral.reward.strategy = new_strategy
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Updated referral reward strategy "
            f"from '{old_strategy}' to '{new_strategy}'"
        )


class UpdateReferralRewardConfig(Interactor[str, None]):
    required_permission = Permission.SETTINGS_REFERRAL

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, input_text: str) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()
            max_allowed_level = settings.referral.level
            new_config = settings.referral.reward.config.copy()
            old_config_str = str(new_config)

            if input_text.isdigit():
                value = int(input_text)

                if value < 1:
                    raise ValueError(f"Reward value '{value}' cannot be negative")

                new_config[ReferralLevel.FIRST] = value
            else:
                for pair in input_text.split():
                    level_str, value_str = pair.split("=")
                    level = ReferralLevel(int(level_str.strip()))

                    if level > max_allowed_level:
                        raise ValueError(f"Level '{level}' is not enabled in settings")

                    value = int(value_str.strip())

                    if value < 1:
                        raise ValueError(
                            f"Reward value '{value}' for level '{level}' cannot be negative"
                        )

                    new_config[level] = value

            settings.referral.reward.config = new_config
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Updated referral reward config from '{old_config_str}' to '{new_config}'"
        )


SETTINGS_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    ChangeAccessMode,
    ToggleConditionRequirement,
    ToggleNotification,
    TogglePayments,
    ToggleReferralSystem,
    ToggleRegistration,
    UpdateChannelRequirement,
    UpdateReferralAccrualStrategy,
    UpdateReferralLevel,
    UpdateReferralRewardConfig,
    UpdateReferralRewardStrategy,
    UpdateReferralRewardType,
    UpdateRulesRequirement,
)
