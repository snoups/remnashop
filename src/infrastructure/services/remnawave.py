from dataclasses import fields, is_dataclass
from datetime import timedelta
from typing import Optional, Union
from uuid import UUID

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import AuthenticationError, ConflictError, NetworkError, NotFoundError
from remnapy.models import (
    CreateUserRequestDto,
    DeleteUserHwidDeviceRequestDto,
    GetStatsResponseDto,
    UpdateUserRequestDto,
    UserResponseDto,
)
from remnapy.models.hwid import HwidDeviceDto

from src.application.common import Remnawave
from src.application.common.remnawave import T
from src.application.dto import PlanSnapshotDto, RemnaSubscriptionDto, SubscriptionDto, UserDto
from src.core.enums import SubscriptionStatus
from src.core.utils.converters import days_to_datetime, gb_to_bytes
from src.core.utils.time import datetime_now


class RemnawaveImpl(Remnawave):
    def __init__(self, sdk: RemnawaveSDK) -> None:
        self.sdk = sdk

    async def try_connection(self) -> None:
        try:
            response = await self.sdk.system.get_stats()
        except AuthenticationError as e:
            logger.error(f"Authentication failed when connecting to Remnawave panel: '{e}'")
            raise
        except NetworkError as e:
            logger.error(f"Network error when connecting to Remnawave panel: '{e}'")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Remnawave panel: '{e}'")
            raise

        if not isinstance(response, GetStatsResponseDto):
            logger.error(f"Invalid response from Remnawave panel: '{response}'")
            raise ValueError(f"Invalid response from Remnawave panel: {response}")

        logger.info("Successfully connected to Remnawave panel")

    async def create_public_user(self, user: UserDto) -> UserResponseDto:
        if not user.login:
            raise ValueError("Web user login is required to create Remnawave user")

        request_dto = CreateUserRequestDto(
            username=user.login,
            expire_at=datetime_now() + timedelta(days=3650),
            email=user.email,
            description=user.remna_description,
            telegram_id=None,
        )

        try:
            remna_user = await self.sdk.users.create_user(request_dto)
            logger.info(
                f"Public RemnaUser '{remna_user.username}' created successfully. "
                f"UUID: '{remna_user.uuid}', email: '{remna_user.email}'"
            )
            return remna_user
        except ConflictError:
            logger.warning(
                f"Public RemnaUser '{request_dto.username}' "
                f"or email '{request_dto.email}' already exists in panel"
            )
            raise

    async def create_user(
        self,
        user: UserDto,
        plan: Optional[PlanSnapshotDto] = None,
        subscription: Optional[SubscriptionDto] = None,
    ) -> UserResponseDto:
        request_dto = self._build_create_request(user, plan, subscription)

        try:
            remna_user = await self.sdk.users.create_user(request_dto)
            logger.info(
                f"RemnaUser '{remna_user.username}' created successfully. "
                f"UUID: '{remna_user.uuid}', telegram_id: '{remna_user.telegram_id}'"
            )
            return remna_user
        except ConflictError:
            logger.warning(
                f"RemnaUser '{request_dto.username}' with UUID '{request_dto.uuid}' "
                f"already exists in panel"
            )
            raise

    async def update_user(
        self,
        user: UserDto,
        uuid: UUID,
        plan: Optional[PlanSnapshotDto] = None,
        subscription: Optional[SubscriptionDto] = None,
        reset_traffic: bool = False,
    ) -> UserResponseDto:
        request_dto = self._build_update_request(user, uuid, plan, subscription)

        try:
            remna_user = await self.sdk.users.update_user(request_dto)
            logger.info(
                f"RemnaUser '{remna_user.username}' updated successfully. "
                f"UUID: '{remna_user.uuid}', telegram_id: '{remna_user.telegram_id}'"
            )
        except NotFoundError:
            logger.warning(
                f"RemnaUser '{request_dto.username}' with UUID '{request_dto.uuid}' not found"
            )
            raise

        if reset_traffic:
            await self.reset_traffic(uuid)

        return remna_user

    async def delete_user(self, uuid: UUID) -> bool:
        try:
            response = await self.sdk.users.delete_user(uuid)
        except NotFoundError:
            logger.debug(f"RemnaUser '{uuid}' not found in panel")
            return False

        if response.is_deleted:
            logger.info(f"RemnaUser '{uuid}' deleted successfully")
        else:
            logger.warning(f"Failed to delete RemnaUser '{uuid}'")

        return response.is_deleted

    async def get_user_by_uuid(self, uuid: UUID) -> Optional[UserResponseDto]:
        try:
            remna_user = await self.sdk.users.get_user_by_uuid(uuid)
            logger.info(f"Fetched RemnaUser '{uuid}' from panel")
            return remna_user
        except NotFoundError:
            logger.debug(f"RemnaUser '{uuid}' not found in panel")
            return None

    async def get_user_by_telegram_id(self, telegram_id: int) -> list[UserResponseDto]:
        response = await self.sdk.users.get_users_by_telegram_id(telegram_id)
        logger.debug(f"Fetched {len(response.root)} RemnaUsers for telegram_id '{telegram_id}'")
        return response.root

    async def get_user_by_email(self, email: str) -> list[UserResponseDto]:
        response = await self.sdk.users.get_users_by_email(email)
        logger.debug(f"Fetched {len(response.root)} RemnaUsers for email '{email}'")
        return response.root

    async def get_devices(self, user_uuid: UUID) -> list[HwidDeviceDto]:
        response = await self.sdk.hwid.get_hwid_user(user_uuid)
        logger.debug(f"Fetched {response.total} devices for RemnaUser '{user_uuid}'")
        return response.devices if response.total else []

    async def delete_device(self, user_uuid: UUID, hwid_uuid: str) -> Optional[int]:
        try:
            response = await self.sdk.hwid.delete_hwid_to_user(
                DeleteUserHwidDeviceRequestDto(user_uuid=user_uuid, hwid=hwid_uuid)
            )
            logger.info(
                f"Deleted HWID device '{hwid_uuid}' for RemnaUser '{user_uuid}'. "
                f"Total devices now: {response.total}"
            )
        except NotFoundError:
            logger.debug(f"RemnaUser '{user_uuid}' not found in panel")
            return None

        return response.total

    async def reset_traffic(self, uuid: UUID) -> Optional[UserResponseDto]:
        try:
            remna_user = await self.sdk.users.reset_user_traffic(uuid)
            logger.info(f"Traffic for RemnaUser '{remna_user.uuid}' reset successfully")
            return remna_user
        except NotFoundError:
            logger.debug(f"RemnaUser '{uuid}' not found in panel")
            return None

    async def revoke_subscription(self, uuid: UUID) -> None:
        try:
            await self.sdk.users.revoke_user_subscription(uuid)
            logger.info(f"Subscription for RemnaUser '{uuid}' revoked successfully")
        except NotFoundError:
            logger.debug(f"RemnaUser '{uuid}' not found in panel")

    def apply_sync(self, target: T, source: Union[SubscriptionDto, RemnaSubscriptionDto]) -> T:
        if not is_dataclass(target) or not is_dataclass(source):
            raise TypeError("Both target and source must be dataclasses")

        target_fields = {f.name for f in fields(target)}
        source_fields = {f.name for f in fields(source)}

        field_map = {"user_remna_id": "uuid"}

        for target_field, source_field in field_map.items():
            if target_field in target_fields and source_field in source_fields:
                old_value = getattr(target, target_field)
                new_value = getattr(source, source_field)

                if old_value != new_value:
                    logger.debug(
                        f"Field '{target_field}' changed from '{old_value}' to '{new_value}'"
                    )
                    setattr(target, target_field, new_value)

        common_fields = target_fields & source_fields

        for field_name in common_fields:
            old_value = getattr(target, field_name)
            new_value = getattr(source, field_name)

            if old_value != new_value:
                logger.debug(f"Field '{field_name}' changed from '{old_value}' to '{new_value}'")
                setattr(target, field_name, new_value)

        return target

    def _build_create_request(
        self,
        user: UserDto,
        plan: Optional[PlanSnapshotDto],
        subscription: Optional[SubscriptionDto],
    ) -> CreateUserRequestDto:
        username = self._resolve_username(user)
        telegram_id = self._resolve_telegram_id(user)

        if subscription:
            return CreateUserRequestDto(
                uuid=subscription.user_remna_id,
                username=username,
                telegram_id=telegram_id,
                expire_at=subscription.expire_at,
                traffic_limit_strategy=subscription.traffic_limit_strategy,
                traffic_limit_bytes=gb_to_bytes(subscription.traffic_limit),
                hwid_device_limit=subscription.device_limit,
                description=user.remna_description,
                email=user.email,
                tag=subscription.tag,
                active_internal_squads=subscription.internal_squads,
                external_squad_uuid=subscription.external_squad,
            )

        if plan:
            return CreateUserRequestDto(
                username=username,
                telegram_id=telegram_id,
                expire_at=days_to_datetime(plan.duration),
                traffic_limit_strategy=plan.traffic_limit_strategy,
                traffic_limit_bytes=gb_to_bytes(plan.traffic_limit),
                hwid_device_limit=plan.device_limit,
                description=user.remna_description,
                email=user.email,
                tag=plan.tag,
                active_internal_squads=plan.internal_squads,
                external_squad_uuid=plan.external_squad,
            )

        raise ValueError("Either 'plan' or 'subscription' must be provided")

    def _build_update_request(
        self,
        user: UserDto,
        uuid: UUID,
        plan: Optional[PlanSnapshotDto],
        subscription: Optional[SubscriptionDto],
    ) -> UpdateUserRequestDto:
        telegram_id = self._resolve_telegram_id(user)

        if subscription:
            return UpdateUserRequestDto(
                uuid=uuid,
                telegram_id=telegram_id,
                expire_at=subscription.expire_at,
                status=(
                    SubscriptionStatus.DISABLED
                    if subscription.status == SubscriptionStatus.DISABLED
                    else SubscriptionStatus.ACTIVE
                ),
                traffic_limit_strategy=subscription.traffic_limit_strategy,
                traffic_limit_bytes=gb_to_bytes(subscription.traffic_limit),
                hwid_device_limit=subscription.device_limit,
                description=user.remna_description,
                email=user.email,
                tag=subscription.tag,
                active_internal_squads=subscription.internal_squads,
                external_squad_uuid=subscription.external_squad,
            )

        if plan:
            return UpdateUserRequestDto(
                uuid=uuid,
                telegram_id=telegram_id,
                expire_at=days_to_datetime(plan.duration),
                status=SubscriptionStatus.ACTIVE,
                traffic_limit_strategy=plan.traffic_limit_strategy,
                traffic_limit_bytes=gb_to_bytes(plan.traffic_limit),
                hwid_device_limit=plan.device_limit,
                description=user.remna_description,
                email=user.email,
                tag=plan.tag,
                active_internal_squads=plan.internal_squads,
                external_squad_uuid=plan.external_squad,
            )

        raise ValueError("Either 'plan' or 'subscription' must be provided")

    def _resolve_username(self, user: UserDto) -> str:
        if user.telegram_id < 0 and user.login:
            return user.login
        return user.remna_name

    def _resolve_telegram_id(self, user: UserDto) -> int | None:
        if user.telegram_id < 0:
            return None
        return user.telegram_id
