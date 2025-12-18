from decimal import Decimal
from io import BytesIO
from typing import Any, List, Optional, cast

from aiogram import Bot
from aiogram.types import BufferedInputFile, Message, TelegramObject
from fluentogram import TranslatorHub
from loguru import logger
from PIL import Image
from qrcode import ERROR_CORRECT_H, QRCode  # type: ignore[attr-defined]
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.constants import ASSETS_DIR, REFERRAL_PREFIX, T_ME
from src.core.enums import (
    MessageEffect,
    PurchaseType,
    ReferralAccrualStrategy,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
    UserNotificationType,
)
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    ReferralDto,
    ReferralRewardDto,
    ReferralSettingsDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.database.models.sql import Referral, ReferralReward
from src.infrastructure.redis import RedisRepository
from src.services.notification import NotificationService
from src.services.settings import SettingsService
from src.services.user import UserService

from .base import BaseService


class ReferralService(BaseService):
    uow: UnitOfWork
    user_service: UserService
    settings_service: SettingsService
    _bot_username: Optional[str]

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
        user_service: UserService,
        settings_service: SettingsService,
        notification_service: NotificationService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.user_service = user_service
        self.settings_service = settings_service
        self.notification_service = notification_service
        self._bot_username: Optional[str] = None

    async def create_referral(
        self,
        referrer: UserDto,
        referred: UserDto,
        level: ReferralLevel,
    ) -> ReferralDto:
        referral = await self.uow.repository.referrals.create_referral(
            Referral(
                referrer_telegram_id=referrer.telegram_id,
                referred_telegram_id=referred.telegram_id,
                level=level,
            )
        )

        await self.user_service.clear_user_cache(referrer.telegram_id)
        await self.user_service.clear_user_cache(referred.telegram_id)
        logger.info(f"Referral created: {referrer.telegram_id} -> {referred.telegram_id}")
        return ReferralDto.from_model(referral)  # type: ignore[return-value]

    async def get_referral_by_referred(self, telegram_id: int) -> Optional[ReferralDto]:
        referral = await self.uow.repository.referrals.get_referral_by_referred(telegram_id)
        return ReferralDto.from_model(referral) if referral else None

    async def get_referrals_by_referrer(self, telegram_id: int) -> List[ReferralDto]:
        referrals = await self.uow.repository.referrals.get_referrals_by_referrer(telegram_id)
        return ReferralDto.from_model_list(referrals)

    async def get_referral_count(self, telegram_id: int) -> int:
        count = await self.uow.repository.referrals.count_referrals_by_referrer(telegram_id)
        logger.debug(f"Retrieved counted '{count}' referrals for user '{telegram_id}'")
        return count

    async def get_reward_count(self, telegram_id: int) -> int:
        count = await self.uow.repository.referrals.count_rewards_by_referrer(telegram_id)
        logger.debug(f"Retrieved counted '{count}' rewards for user '{telegram_id}'")
        return count

    async def get_total_rewards_amount(
        self,
        telegram_id: int,
        reward_type: ReferralRewardType,
    ) -> int:
        total_amount = await self.uow.repository.referrals.sum_rewards_by_user(
            telegram_id,
            reward_type,
        )
        logger.debug(
            f"Retrieved calculated total rewards amount as '{total_amount}' "
            f"for user 'user_telegram_id' for type '{reward_type.name}'"
        )
        return total_amount

    async def create_reward(
        self,
        referral_id: int,
        user_telegram_id: int,
        type: ReferralRewardType,
        amount: int,
    ) -> ReferralRewardDto:
        reward = await self.uow.repository.referrals.create_reward(
            ReferralReward(
                referral_id=referral_id,
                user_telegram_id=user_telegram_id,
                type=type,
                amount=amount,
                is_issued=False,
            )
        )
        logger.info(f"ReferralReward '{referral_id} created, user '{user_telegram_id}'")
        return ReferralRewardDto.from_model(reward)  # type: ignore[return-value]

    async def get_rewards_by_user(self, telegram_id: int) -> List[ReferralRewardDto]:
        rewards = await self.uow.repository.referrals.get_rewards_by_user(telegram_id)
        return ReferralRewardDto.from_model_list(rewards)

    async def get_rewards_by_referral(self, referral_id: int) -> List[ReferralRewardDto]:
        rewards = await self.uow.repository.referrals.get_rewards_by_referral(referral_id)
        return ReferralRewardDto.from_model_list(rewards)

    #

    async def mark_reward_as_issued(self, reward_id: int) -> None:
        await self.uow.repository.referrals.update_reward(reward_id, is_issued=True)
        logger.info(f"Marked reward '{reward_id}' as issued")

    async def handle_referral(self, user: UserDto, code: Optional[str]) -> None:
        if not code:
            return

        code = code[len(REFERRAL_PREFIX) :] if code.startswith(REFERRAL_PREFIX) else code

        referrer = await self._get_valid_referrer(code, user.telegram_id)

        if not referrer:
            return

        existing, parent = await self._get_referral_chain(user.telegram_id)

        if existing:
            logger.warning(f"Referral skipped: user '{user.telegram_id}' already referred")
            return

        level = self._define_referral_level(parent.level if parent else None)
        logger.info(
            f"Referral detected '{referrer.telegram_id}' -> '{user.telegram_id}', "
            f"level '{level.name}'"
        )

        await self.create_referral(referrer, user, level)

        if await self.settings_service.is_referral_enable():
            await self.notification_service.notify_user(
                user=referrer,
                ntf_type=UserNotificationType.REFERRAL_ATTACHED,
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-user-referral-attached",
                    i18n_kwargs={"name": user.name},
                    message_effect=MessageEffect.CONFETTI,
                ),
            )

    async def assign_referral_rewards(self, transaction: TransactionDto) -> None:
        from src.infrastructure.taskiq.tasks.referrals import (  # noqa: PLC0415
            give_referrer_reward_task,
        )

        settings = await self.settings_service.get_referral_settings()

        if (
            settings.accrual_strategy == ReferralAccrualStrategy.ON_FIRST_PAYMENT
            and transaction.purchase_type != PurchaseType.NEW
        ):
            logger.info(
                f"Skip rewards: transaction '{transaction.id}' purchase type "
                f"'{transaction.purchase_type}' is not NEW"
            )
            return

        user = transaction.user

        if not user:
            raise ValueError(f"Transaction '{transaction.id}' has no user; cannot assign rewards")

        referral, parent = await self._get_referral_chain(user.telegram_id)

        if not referral:
            logger.info(f"User '{user.telegram_id}' not referred; reward assignment skipped")
            return

        reward_type = settings.reward.type
        reward_chain = {
            ReferralLevel.FIRST: referral.referrer,
        }

        if parent:
            reward_chain[ReferralLevel.SECOND] = parent.referrer

        for level, referrer in reward_chain.items():
            if level > settings.level:
                continue

            config_value = settings.reward.config.get(level)

            if config_value is None:
                logger.info(f"No reward config for level '{level.name}'")
                continue

            reward_amount = self._calculate_reward_amount(
                settings=settings,
                transaction=transaction,
                config_value=config_value,
            )

            if not reward_amount or reward_amount <= 0:
                logger.warning(
                    f"Reward amount <= 0 for referrer '{referrer.telegram_id}', "
                    f"level '{level.name}'"
                )
                continue

            reward = await self.create_reward(
                referral_id=referral.id,  # type: ignore[arg-type]
                user_telegram_id=referrer.telegram_id,
                type=reward_type,
                amount=reward_amount,
            )

            await give_referrer_reward_task.kiq(
                user_telegram_id=referrer.telegram_id,
                reward=reward,
                referred_name=user.name,
            )

            logger.info(
                f"Issued '{reward_type}' reward '{reward_amount}' for referrer "
                f"'{referrer.telegram_id}' (level '{level.name}')"
            )

    async def get_ref_link(self, referral_code: str) -> str:
        return f"{await self._get_bot_redirect_url()}?start={REFERRAL_PREFIX}{referral_code}"

    def get_ref_qr(self, url: str) -> BufferedInputFile:
        qr: Any = QRCode(
            version=1,
            error_correction=ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )

        qr.add_data(url)
        qr.make(fit=True)

        qr_img_raw = qr.make_image(fill_color="black", back_color="white")
        qr_img: Image.Image
        if hasattr(qr_img_raw, "get_image"):
            qr_img = cast(Image.Image, qr_img_raw.get_image())
        else:
            qr_img = cast(Image.Image, qr_img_raw)

        qr_img = qr_img.convert("RGB")

        logo_path = ASSETS_DIR / "logo.png"
        if logo_path.exists():
            logo = Image.open(logo_path).convert("RGBA")

            qr_width, qr_height = qr_img.size
            logo_size = int(qr_width * 0.2)
            logo = logo.resize((logo_size, logo_size), resample=Image.Resampling.LANCZOS)

            pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
            qr_img.paste(logo, pos, mask=logo)

        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)

        return BufferedInputFile(file=buffer.getvalue(), filename="ref_qr.png")

    async def get_referrer_by_event(
        self,
        event: TelegramObject,
        user_telegram_id: int,
    ) -> Optional[UserDto]:
        if not isinstance(event, Message) or not event.text:
            return None

        code = self._parse_referral_code(event.text)

        if not code:
            return None

        return await self._get_valid_referrer(code, user_telegram_id)

    async def get_ref_code_by_event(self, event: TelegramObject) -> Optional[str]:
        if not isinstance(event, Message) or not event.text:
            return None

        return self._parse_referral_code(event.text)

    async def is_referral_event(self, event: TelegramObject, user_telegram_id: int) -> bool:
        if not isinstance(event, Message) or not event.text:
            return False

        code = self._parse_referral_code(event.text)

        if not code:
            return False

        return bool(await self._get_valid_referrer(code, user_telegram_id))

    def _define_referral_level(self, parent_level: Optional[ReferralLevel]) -> ReferralLevel:
        if parent_level is None:
            return ReferralLevel.FIRST

        next_level_value = parent_level.value + 1
        max_level_value = max(item.value for item in ReferralLevel)

        if next_level_value > max_level_value:
            return ReferralLevel(parent_level.value)

        return ReferralLevel(next_level_value)

    async def _get_bot_redirect_url(self) -> str:
        if self._bot_username is None:
            self._bot_username = (await self.bot.get_me()).username

        return f"{T_ME}{self._bot_username}"

    def _parse_referral_code(self, text: str) -> Optional[str]:
        parts = text.split()

        if len(parts) <= 1:
            return None

        code = parts[1]

        if not code.startswith(REFERRAL_PREFIX):
            return None

        return code[len(REFERRAL_PREFIX) :]

    async def _get_valid_referrer(self, code: str, user_id: int) -> Optional[UserDto]:
        referrer = await self.user_service.get_by_referral_code(code)

        if not referrer or referrer.telegram_id == user_id:
            logger.warning(f"Invalid referral code '{code}' or self-referral by '{user_id}'")
            return None

        return referrer

    async def _get_referral_chain(
        self,
        user_id: int,
    ) -> tuple[Optional[ReferralDto], Optional[ReferralDto]]:
        referral = await self.get_referral_by_referred(user_id)
        parent = None

        if referral:
            parent = await self.get_referral_by_referred(referral.referrer.telegram_id)

        return referral, parent

    def _calculate_reward_amount(
        self,
        settings: ReferralSettingsDto,
        transaction: TransactionDto,
        config_value: int,
    ) -> Optional[int]:
        reward_strategy = settings.reward.strategy
        reward_type = settings.reward.type
        reward_amount: int

        if reward_strategy == ReferralRewardStrategy.AMOUNT:
            reward_amount = config_value

        elif reward_strategy == ReferralRewardStrategy.PERCENT:
            percentage = Decimal(config_value) / Decimal(100)

            if reward_type == ReferralRewardType.POINTS:
                base_amount = transaction.pricing.final_amount
                reward_amount = max(1, int(base_amount * percentage))

            elif reward_type == ReferralRewardType.EXTRA_DAYS:
                if transaction.plan and transaction.plan.duration:
                    base_amount = Decimal(transaction.plan.duration)
                    reward_amount = max(1, int(base_amount * percentage))
                else:
                    logger.warning(
                        f"Cannot calculate extra days reward, plan duration is missing "
                        f"for transaction '{transaction.id}'"
                    )
                    return None
            else:
                logger.warning(f"Unsupported reward type '{reward_type}' for PERCENT strategy")
                return None

        else:
            logger.warning(f"Unsupported reward strategy '{reward_strategy}'")
            return None

        return reward_amount
