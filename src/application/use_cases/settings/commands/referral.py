from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import SettingsDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import UserDto
from src.core.enums import (
    ReferralAccrualStrategy,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
)


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


class ToggleReferralTrialReward(Interactor[None, bool]):
    required_permission = Permission.SETTINGS_REFERRAL

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, data: None) -> bool:
        async with self.uow:
            settings = await self.settings_dao.get()
            old_status = settings.referral.reward_for_trial
            settings.referral.reward_for_trial = not old_status
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(
            f"{actor.log} Toggled referral trial reward "
            f"from '{old_status}' to '{settings.referral.reward_for_trial}'"
        )
        return settings.referral.reward_for_trial


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
