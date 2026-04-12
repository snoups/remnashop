import base64
import asyncio
import hashlib
import hmac
import json
import secrets
import smtplib
import time
from decimal import Decimal
from datetime import timedelta
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Annotated, Optional
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from remnapy.exceptions import ConflictError
from remnapy.models.hwid import HwidDeviceDto
from sqlalchemy.exc import IntegrityError

from src.application.common import Cryptographer, Remnawave
from src.application.common.dao import (
    PaymentGatewayDao,
    PlanDao,
    ReferralDao,
    SettingsDao,
    SubscriptionDao,
    TransactionDao,
    UserDao,
)
from src.application.common.uow import UnitOfWork
from src.application.dto import PlanDto, PlanSnapshotDto, SubscriptionDto, UserDto
from src.application.services import PricingService
from src.application.use_cases.gateways.commands.payment import (
    CreatePayment,
    CreatePaymentDto,
)
from src.application.use_cases.plan.queries.match import MatchPlan, MatchPlanDto
from src.application.use_cases.referral.commands.attachment import (
    AttachReferral,
    AttachReferralDto,
)
from src.application.use_cases.remnawave.commands.management import (
    DeleteUserDevice,
    DeleteUserDeviceDto,
)
from src.application.use_cases.user.queries.plans import GetAvailablePlans
from src.core.config import AppConfig
from src.core.constants import (
    API_V1, 
    PASSWORD_SCRYPT_DKLEN,
    PASSWORD_SCRYPT_N,
    PASSWORD_SCRYPT_P,
    PASSWORD_SCRYPT_R,
    PUBLIC_LANDING_PLANS_CACHE_TTL_SECONDS,
    EMAIL_VERIFICATION_CODE_LENGTH,
    ACCESS_TOKEN_TTL_SECONDS
)
from src.core.enums import (
    Currency,
    PaymentGatewayType,
    PlanAvailability,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from src.core.types import RemnaUserDto
from src.core.utils.converters import days_to_datetime
from src.core.utils.time import datetime_now

router = APIRouter(prefix=API_V1 + "/public", tags=['Public'])

_public_landing_plans_cache: Optional["PublicPlanLandingListResponse"] = None
_public_landing_plans_cache_expires_at: Optional[datetime] = None


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    login: str = Field(min_length=3, max_length=36, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=256)
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    referral_code: Optional[str] = Field(default=None, min_length=3, max_length=64)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return value.lower()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("referral_code")
    @classmethod
    def normalize_referral_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    login: str = Field(min_length=3, max_length=36)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return value.lower()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class MigrateTelegramRequest(RegisterRequest):
    pass


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class MeResponse(BaseModel):
    telegram_id: int
    login: Optional[str]
    email: Optional[str]
    is_email_verified: bool
    pending_email: Optional[str]
    name: str
    username: Optional[str]
    language: str


class SubscriptionInfoResponse(BaseModel):
    has_subscription: bool
    user_remna_id: Optional[str] = None
    status: Optional[str] = None
    is_trial: Optional[bool] = None
    traffic_limit: Optional[int] = None
    device_limit: Optional[int] = None
    traffic_limit_strategy: Optional[str] = None
    expire_at: Optional[datetime] = None
    url: Optional[str] = None
    plan_name: Optional[str] = None
    plan_duration_days: Optional[int] = None
    used_traffic_bytes: Optional[int] = None
    lifetime_used_traffic_bytes: Optional[int] = None
    online_at: Optional[datetime] = None


class DeviceResponse(BaseModel):
    hwid: str
    platform: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    user_agent: Optional[str] = None


class DevicesResponse(BaseModel):
    devices: list[DeviceResponse]
    current_count: int
    max_count: int


class DeviceDeleteResponse(BaseModel):
    deleted: bool


class ReissueResponse(BaseModel):
    success: bool


class ChangePasswordResponse(BaseModel):
    success: bool


class RequestEmailVerificationCodeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: Optional[str] = Field(
        default=None,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.lower()


class ChangeEmailRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class ChangeEmailResponse(BaseModel):
    success: bool
    pending_email: str


class RequestEmailVerificationCodeResponse(BaseModel):
    success: bool
    target_email: str
    expires_at: datetime


class ConfirmEmailVerificationRequest(BaseModel):
    code: str = Field(
        min_length=EMAIL_VERIFICATION_CODE_LENGTH,
        max_length=EMAIL_VERIFICATION_CODE_LENGTH,
        pattern=r"^\d{6}$",
    )


class ConfirmEmailVerificationResponse(BaseModel):
    success: bool
    email: str


class PurchaseRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    plan_code: str = Field(min_length=3, max_length=64)
    duration_days: int = Field(ge=0)
    gateway_type: PaymentGatewayType


class ExtendRequest(BaseModel):
    duration_days: int = Field(ge=0)
    gateway_type: PaymentGatewayType


class PaymentInitResponse(BaseModel):
    payment_id: str
    payment_url: Optional[str] = None
    purchase_type: str
    status: str
    is_free: bool
    final_amount: str
    currency: str


class GatewayOfferResponse(BaseModel):
    gateway_type: PaymentGatewayType
    currency: str
    currency_symbol: str


class DurationGatewayPriceResponse(BaseModel):
    gateway_type: PaymentGatewayType
    currency: str
    currency_symbol: str
    original_amount: str
    discount_percent: int
    final_amount: str
    is_free: bool


class DurationOfferResponse(BaseModel):
    days: int
    prices: list[DurationGatewayPriceResponse]


class PlanOfferResponse(BaseModel):
    id: int
    public_code: str
    name: str
    description: Optional[str] = None
    traffic_limit: int
    device_limit: int
    type: str
    recommended_purchase_type: str
    durations: list[DurationOfferResponse]


class SubscriptionOffersResponse(BaseModel):
    gateways: list[GatewayOfferResponse]
    plans: list[PlanOfferResponse]
    has_current_subscription: bool
    current_subscription_status: Optional[str] = None


class PublicPlanLandingResponse(BaseModel):
    public_code: str
    name: str
    description: Optional[str] = None
    traffic_limit: int
    device_limit: int
    monthly_from_rub: str
    max_duration_days: int
    max_duration_price_rub: str


class PublicPlanLandingListResponse(BaseModel):
    plans: list[PublicPlanLandingResponse]


class ReferralRewardLevelResponse(BaseModel):
    level: int
    value: int


class ReferralProgramResponse(BaseModel):
    enabled: bool
    referral_code: str
    invited_count: int
    invited_with_payment_count: int
    reward_type: str
    reward_strategy: str
    accrual_strategy: str
    max_level: int
    reward_levels: list[ReferralRewardLevelResponse]


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _normalize_decimal_str(value: Decimal) -> str:
    if value == value.to_integral():
        return str(int(value))

    normalized = value.quantize(Decimal("0.01")).normalize()
    return format(normalized, "f")


def _hash_password(password: str, key: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password=f"{password}:{key}".encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=PASSWORD_SCRYPT_DKLEN,
    )
    return (
        f"scrypt${PASSWORD_SCRYPT_N}${PASSWORD_SCRYPT_R}${PASSWORD_SCRYPT_P}"
        f"${_b64url_encode(salt)}${_b64url_encode(digest)}"
    )


def _verify_password(password: str, password_hash: str, key: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, digest_b64 = password_hash.split("$", maxsplit=5)
        if algorithm != "scrypt":
            return False

        expected_digest = _b64url_decode(digest_b64)
        check_digest = hashlib.scrypt(
            password=f"{password}:{key}".encode("utf-8"),
            salt=_b64url_decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_digest),
        )
        return hmac.compare_digest(expected_digest, check_digest)
    except Exception:
        return False


def _generate_email_verification_code() -> str:
    lower = 10 ** (EMAIL_VERIFICATION_CODE_LENGTH - 1)
    upper = (10**EMAIL_VERIFICATION_CODE_LENGTH) - 1
    return str(secrets.randbelow(upper - lower + 1) + lower)


def _hash_email_verification_code(code: str, key: str) -> str:
    payload = f"{code}:{key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_email_delivery_enabled(config: AppConfig) -> bool:
    return bool(
        config.email.enabled
        and config.email.host
        and config.email.from_email
        and config.email.username.get_secret_value()
        and config.email.password.get_secret_value()
    )


def _send_email_verification_code_sync(
    *,
    config: AppConfig,
    target_email: str,
    verification_code: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = "Oldnet: подтверждение email"
    from_name = config.email.from_name.strip()
    from_email = config.email.from_email.strip()
    message["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    message["To"] = target_email
    message.set_content(
        "Ваш код подтверждения: "
        f"{verification_code}\n\n"
        f"Код действует {config.email.verification_code_ttl_minutes} минут."
    )

    smtp_host = config.email.host
    smtp_port = config.email.port
    smtp_user = config.email.username.get_secret_value()
    smtp_password = config.email.password.get_secret_value()

    if config.email.use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as client:
            client.login(smtp_user, smtp_password)
            client.send_message(message)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as client:
        client.ehlo()
        if config.email.use_tls:
            client.starttls()
            client.ehlo()
        client.login(smtp_user, smtp_password)
        client.send_message(message)


async def _send_email_verification_code(
    *,
    config: AppConfig,
    target_email: str,
    verification_code: str,
) -> None:
    try:
        await asyncio.to_thread(
            _send_email_verification_code_sync,
            config=config,
            target_email=target_email,
            verification_code=verification_code,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send verification email: {e}",
        ) from e


def _generate_access_token(subject: int, key: str) -> tuple[str, datetime]:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    issued_at = int(time.time())
    expires_at = issued_at + ACCESS_TOKEN_TTL_SECONDS
    payload = _b64url_encode(
        json.dumps({"sub": subject, "iat": issued_at, "exp": expires_at}).encode("utf-8")
    )

    signature = hmac.new(
        key.encode("utf-8"),
        f"{header}.{payload}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = f"{header}.{payload}.{_b64url_encode(signature)}"
    expires_at_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    return token, expires_at_dt


def _decode_access_token(token: str, key: str) -> dict[str, int]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        ) from e

    expected_signature = hmac.new(
        key.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("utf-8"),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(expected_signature, _b64url_decode(signature_b64)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
        )

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    return payload


def _generate_virtual_telegram_id() -> int:
    return -secrets.randbelow(9_000_000_000_000_000) - 1


async def _build_auth_response(user: UserDto, config: AppConfig) -> AuthResponse:
    access_token, expires_at = _generate_access_token(
        subject=user.telegram_id,
        key=config.crypt_key.get_secret_value(),
    )
    return AuthResponse(access_token=access_token, expires_at=expires_at)


def _to_device_response(device: HwidDeviceDto) -> DeviceResponse:
    return DeviceResponse(
        hwid=device.hwid,
        platform=device.platform,
        device_model=device.device_model,
        os_version=device.os_version,
        user_agent=device.user_agent,
    )


def _assert_web_gateway(gateway_type: PaymentGatewayType) -> None:
    if gateway_type == PaymentGatewayType.TELEGRAM_STARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TELEGRAM_STARS gateway is not available for web purchase",
        )


def _assert_web_purchase_email_verified(user: UserDto) -> None:
    if user.is_email_verified:
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Email must be verified before purchasing or extending a subscription",
    )


async def _get_available_plan_by_code(
    user: UserDto,
    plan_code: str,
    get_available_plans: GetAvailablePlans,
) -> Optional[PlanDto]:
    plans = await get_available_plans.system(user)
    return next((plan for plan in plans if plan.public_code == plan_code), None)


async def _validate_gateway_for_web(
    gateway_type: PaymentGatewayType,
    payment_gateway_dao: PaymentGatewayDao,
) -> None:
    _assert_web_gateway(gateway_type)
    gateway = await payment_gateway_dao.get_by_type(gateway_type)
    if not gateway or not gateway.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway '{gateway_type}' not found or inactive",
        )

    if not gateway.settings or not gateway.settings.is_configured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Gateway '{gateway_type}' is not configured",
        )


def _build_subscription_dto_for_web(
    *,
    remna_user: RemnaUserDto,
    plan: PlanSnapshotDto,
) -> SubscriptionDto:
    return SubscriptionDto(
        user_remna_id=remna_user.uuid,
        status=SubscriptionStatus(remna_user.status),
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        traffic_limit_strategy=plan.traffic_limit_strategy,
        tag=plan.tag,
        internal_squads=plan.internal_squads,
        external_squad=plan.external_squad,
        expire_at=remna_user.expire_at,
        url=remna_user.subscription_url,
        plan_snapshot=plan,
    )


async def _complete_free_purchase(
    *,
    user: UserDto,
    payment_id: str,
    uow: UnitOfWork,
    transaction_dao: TransactionDao,
    subscription_dao: SubscriptionDao,
    user_dao: UserDao,
    remnawave: Remnawave,
) -> None:
    async with uow:
        transaction_uuid = UUID(payment_id)
        transaction = await transaction_dao.update_status(
            payment_id=transaction_uuid,
            status=TransactionStatus.COMPLETED,
        )
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction '{payment_id}' not found",
            )

        current_subscription = await subscription_dao.get_current(user.telegram_id)
        plan = transaction.plan_snapshot
        purchase_type = transaction.purchase_type
        has_trial = current_subscription.is_trial if current_subscription else False

        if purchase_type == PurchaseType.NEW and not has_trial:
            existing_remna_user = None
            if user.email:
                candidates = await remnawave.get_user_by_email(user.email)
                if user.login:
                    existing_remna_user = next(
                        (candidate for candidate in candidates if candidate.username == user.login),
                        None,
                    )
                if not existing_remna_user and candidates:
                    existing_remna_user = candidates[0]

            if existing_remna_user:
                created_user = await remnawave.update_user(
                    user=user,
                    uuid=existing_remna_user.uuid,
                    plan=plan,
                    reset_traffic=True,
                )
            else:
                created_user = await remnawave.create_user(user, plan=plan)
            new_sub = _build_subscription_dto_for_web(remna_user=created_user, plan=plan)
            await subscription_dao.create(subscription=new_sub, telegram_id=user.telegram_id)
            await user_dao.set_trial_available(user.telegram_id, False)

        elif purchase_type == PurchaseType.RENEW and not has_trial:
            if not current_subscription:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No subscription found for renewal for '{user.telegram_id}'",
                )

            duration = plan.duration
            if duration == 0:
                new_expire = days_to_datetime(duration)
            else:
                base_date = max(current_subscription.expire_at, datetime_now())
                new_expire = base_date + timedelta(days=duration)

            current_subscription.expire_at = new_expire
            await remnawave.update_user(
                user=user,
                uuid=current_subscription.user_remna_id,
                subscription=current_subscription,
                reset_traffic=True,
            )
            current_subscription.plan_snapshot = plan
            await subscription_dao.update(current_subscription)

        elif purchase_type == PurchaseType.CHANGE or has_trial:
            if not current_subscription:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No subscription found for change for '{user.telegram_id}'",
                )

            await subscription_dao.update_status(
                subscription_id=current_subscription.id,  # type: ignore[arg-type]
                status=SubscriptionStatus.DELETED,
            )
            updated_user = await remnawave.update_user(
                user=user,
                uuid=current_subscription.user_remna_id,
                plan=plan,
                reset_traffic=True,
            )
            new_sub = _build_subscription_dto_for_web(remna_user=updated_user, plan=plan)
            await subscription_dao.create(subscription=new_sub, telegram_id=user.telegram_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown purchase type '{purchase_type}' for '{user.telegram_id}'",
            )

        await uow.commit()


async def _get_user_from_auth_header(
    authorization: Annotated[Optional[str], Header(alias="Authorization")],
    user_dao: UserDao,
    config: AppConfig,
) -> UserDto:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer token",
        )

    token = authorization.removeprefix("Bearer ").strip()
    payload = _decode_access_token(token, config.crypt_key.get_secret_value())
    telegram_id = int(payload["sub"])
    user = await user_dao.get_by_telegram_id(telegram_id)
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


@router.get("/plans/public", response_model=PublicPlanLandingListResponse)
@inject
async def get_public_landing_plans(
    plan_dao: FromDishka[PlanDao],
) -> PublicPlanLandingListResponse:
    global _public_landing_plans_cache, _public_landing_plans_cache_expires_at

    now = datetime_now()
    if (
        _public_landing_plans_cache is not None
        and _public_landing_plans_cache_expires_at is not None
        and _public_landing_plans_cache_expires_at > now
    ):
        return _public_landing_plans_cache

    plans = await plan_dao.filter_by_availability(PlanAvailability.ALL)

    result: list[PublicPlanLandingResponse] = []
    for plan in plans:
        if not plan.is_active or plan.is_trial or not plan.public_code:
            continue

        rub_duration_candidates: list[tuple[int, Decimal]] = []
        for duration in plan.durations:
            if duration.days <= 0:
                continue

            rub_price = next((p.price for p in duration.prices if p.currency == Currency.RUB), None)
            if rub_price is not None:
                rub_duration_candidates.append((duration.days, rub_price))

        if not rub_duration_candidates:
            continue

        max_duration_days, max_duration_price = max(
            rub_duration_candidates,
            key=lambda item: item[0],
        )
        monthly_from = (max_duration_price * Decimal(30)) / Decimal(max_duration_days)

        result.append(
            PublicPlanLandingResponse(
                public_code=plan.public_code,
                name=plan.name,
                description=plan.description,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                monthly_from_rub=_normalize_decimal_str(monthly_from),
                max_duration_days=max_duration_days,
                max_duration_price_rub=_normalize_decimal_str(max_duration_price),
            )
        )

    payload = PublicPlanLandingListResponse(plans=result)
    _public_landing_plans_cache = payload
    _public_landing_plans_cache_expires_at = now + timedelta(
        seconds=PUBLIC_LANDING_PLANS_CACHE_TTL_SECONDS
    )
    return payload


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@inject
async def register_public_user(
    body: RegisterRequest,
    config: FromDishka[AppConfig],
    uow: FromDishka[UnitOfWork],
    user_dao: FromDishka[UserDao],
    cryptographer: FromDishka[Cryptographer],
    remnawave: FromDishka[Remnawave],
    attach_referral: FromDishka[AttachReferral],
) -> AuthResponse:
    if await user_dao.get_by_login(body.login):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already exists")
    if await user_dao.get_by_email(body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    if body.referral_code and not await user_dao.get_by_referral_code(body.referral_code):
        body.referral_code = None

    for _ in range(10):
        telegram_id = _generate_virtual_telegram_id()
        if not await user_dao.exists(telegram_id):
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot allocate user id, retry later",
        )

    new_user = UserDto(
        telegram_id=telegram_id,
        login=body.login,
        email=body.email,
        password_hash=_hash_password(body.password, config.crypt_key.get_secret_value()),
        username=None,
        name=body.name or body.login,
        referral_code=cryptographer.generate_short_code(telegram_id, length=12),
        language=config.default_locale,
    )

    async with uow:
        try:
            created = await user_dao.create(new_user)
            await remnawave.create_public_user(created)
            await uow.commit()
        except ConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists in Remnawave",
            ) from e
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this login or email already exists",
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to create user in Remnawave: {e}",
            ) from e

    if body.referral_code:
        await attach_referral.system(
            AttachReferralDto(
                user_telegram_id=created.telegram_id,
                referral_code=body.referral_code,
            )
        )

    return await _build_auth_response(created, config)


@router.post("/auth/login", response_model=AuthResponse)
@inject
async def login_public_user(
    body: LoginRequest,
    config: FromDishka[AppConfig],
    user_dao: FromDishka[UserDao],
) -> AuthResponse:
    user = await user_dao.get_by_login(body.login)
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login or password",
        )

    if not _verify_password(body.password, user.password_hash, config.crypt_key.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login or password",
        )

    return await _build_auth_response(user, config)


@router.get("/auth/me", response_model=MeResponse)
@inject
async def get_public_user_profile(
    config: FromDishka[AppConfig],
    user_dao: FromDishka[UserDao],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> MeResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    return MeResponse(
        telegram_id=user.telegram_id,
        login=user.login,
        email=user.email,
        is_email_verified=user.is_email_verified,
        pending_email=user.pending_email,
        name=user.name,
        username=user.username,
        language=user.language.value,
    )


@router.post("/auth/change-password", response_model=ChangePasswordResponse)
@inject
async def change_public_user_password(
    body: ChangePasswordRequest,
    config: FromDishka[AppConfig],
    uow: FromDishka[UnitOfWork],
    user_dao: FromDishka[UserDao],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> ChangePasswordResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    key = config.crypt_key.get_secret_value()

    if not _verify_password(body.current_password, user.password_hash or "", key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is invalid",
        )

    if _verify_password(body.new_password, user.password_hash or "", key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="New password must be different from current password",
        )

    user.password_hash = _hash_password(body.new_password, key)

    async with uow:
        updated = await user_dao.update(user)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found during password update",
            )
        await uow.commit()

    return ChangePasswordResponse(success=True)


@router.post(
    "/auth/email/change",
    response_model=ChangeEmailResponse,
)
@inject
async def change_email(
    body: ChangeEmailRequest,
    config: FromDishka[AppConfig],
    uow: FromDishka[UnitOfWork],
    user_dao: FromDishka[UserDao],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> ChangeEmailResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    if user.email and user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email change is available only for users without verified email",
        )

    existing = await user_dao.get_by_email(body.email)
    if existing and existing.telegram_id != user.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    user.pending_email = body.email
    user.is_email_verified = False
    user.email_verification_code_hash = None
    user.email_verification_expires_at = None

    async with uow:
        updated = await user_dao.update(user)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found during email change",
            )
        await uow.commit()

    return ChangeEmailResponse(success=True, pending_email=body.email)


@router.post(
    "/auth/email/request-verification",
    response_model=RequestEmailVerificationCodeResponse,
)
@inject
async def request_email_verification_code(
    body: RequestEmailVerificationCodeRequest,
    config: FromDishka[AppConfig],
    uow: FromDishka[UnitOfWork],
    user_dao: FromDishka[UserDao],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> RequestEmailVerificationCodeResponse:
    if not _is_email_delivery_enabled(config):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured",
        )

    user = await _get_user_from_auth_header(authorization, user_dao, config)

    requested_email = body.email
    if requested_email and user.email and user.is_email_verified and requested_email != user.email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email change is available only for users without verified email",
        )

    if requested_email and requested_email != user.email:
        existing = await user_dao.get_by_email(requested_email)
        if existing and existing.telegram_id != user.telegram_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )
        user.pending_email = requested_email
        user.is_email_verified = False
    elif requested_email and requested_email == user.email and user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already verified",
        )

    target_email = user.pending_email or user.email
    if not target_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required for verification",
        )

    code = _generate_email_verification_code()
    user.email_verification_code_hash = _hash_email_verification_code(
        code,
        config.crypt_key.get_secret_value(),
    )
    user.email_verification_expires_at = datetime_now() + timedelta(
        minutes=config.email.verification_code_ttl_minutes
    )

    async with uow:
        updated = await user_dao.update(user)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found during email verification request",
            )
        await uow.commit()

    await _send_email_verification_code(
        config=config,
        target_email=target_email,
        verification_code=code,
    )

    return RequestEmailVerificationCodeResponse(
        success=True,
        target_email=target_email,
        expires_at=user.email_verification_expires_at,  # type: ignore[arg-type]
    )


@router.post(
    "/auth/email/confirm",
    response_model=ConfirmEmailVerificationResponse,
)
@inject
async def confirm_email_verification(
    body: ConfirmEmailVerificationRequest,
    config: FromDishka[AppConfig],
    uow: FromDishka[UnitOfWork],
    user_dao: FromDishka[UserDao],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> ConfirmEmailVerificationResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    if not user.email_verification_code_hash or not user.email_verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification was not requested",
        )

    if user.email_verification_expires_at < datetime_now():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Verification code has expired",
        )

    incoming_hash = _hash_email_verification_code(body.code, config.crypt_key.get_secret_value())
    if not hmac.compare_digest(incoming_hash, user.email_verification_code_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    verified_email = user.pending_email or user.email
    if not verified_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email to confirm",
        )

    if user.pending_email:
        existing = await user_dao.get_by_email(user.pending_email)
        if existing and existing.telegram_id != user.telegram_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )
        user.email = user.pending_email

    user.pending_email = None
    user.is_email_verified = True
    user.email_verification_code_hash = None
    user.email_verification_expires_at = None

    async with uow:
        updated = await user_dao.update(user)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found during email confirmation",
            )
        await uow.commit()

    return ConfirmEmailVerificationResponse(
        success=True,
        email=verified_email,
    )

@router.get("/subscription/current", response_model=SubscriptionInfoResponse)
@inject
async def get_current_subscription(
    config: FromDishka[AppConfig],
    user_dao: FromDishka[UserDao],
    subscription_dao: FromDishka[SubscriptionDao],
    remnawave: FromDishka[Remnawave],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> SubscriptionInfoResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    current_subscription = await subscription_dao.get_current(user.telegram_id)

    if not current_subscription:
        return SubscriptionInfoResponse(has_subscription=False)

    remna_user = await remnawave.get_user_by_uuid(current_subscription.user_remna_id)

    return SubscriptionInfoResponse(
        has_subscription=True,
        user_remna_id=str(current_subscription.user_remna_id),
        status=current_subscription.current_status.value,
        is_trial=current_subscription.is_trial,
        traffic_limit=current_subscription.traffic_limit,
        device_limit=current_subscription.device_limit,
        traffic_limit_strategy=current_subscription.traffic_limit_strategy.value,
        expire_at=current_subscription.expire_at,
        url=current_subscription.url,
        plan_name=current_subscription.plan_snapshot.name,
        plan_duration_days=current_subscription.plan_snapshot.duration,
        used_traffic_bytes=remna_user.used_traffic_bytes if remna_user else None,
        lifetime_used_traffic_bytes=remna_user.lifetime_used_traffic_bytes if remna_user else None,
        online_at=remna_user.online_at if remna_user else None,
    )


@router.get("/subscription/devices", response_model=DevicesResponse)
@inject
async def get_subscription_devices(
    config: FromDishka[AppConfig],
    user_dao: FromDishka[UserDao],
    subscription_dao: FromDishka[SubscriptionDao],
    remnawave: FromDishka[Remnawave],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> DevicesResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    current_subscription = await subscription_dao.get_current(user.telegram_id)
    if not current_subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    devices = await remnawave.get_devices(current_subscription.user_remna_id)
    return DevicesResponse(
        devices=[_to_device_response(device) for device in devices],
        current_count=len(devices),
        max_count=current_subscription.device_limit,
    )


@router.delete("/subscription/devices/{hwid}", response_model=DeviceDeleteResponse)
@inject
async def delete_subscription_device(
    hwid: str,
    config: FromDishka[AppConfig],
    user_dao: FromDishka[UserDao],
    delete_user_device: FromDishka[DeleteUserDevice],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> DeviceDeleteResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    deleted = await delete_user_device(
        user,
        DeleteUserDeviceDto(telegram_id=user.telegram_id, hwid=hwid),
    )
    return DeviceDeleteResponse(deleted=deleted)


# @router.post("/subscription/reissue", response_model=ReissueResponse)
# @inject
# async def reissue_current_subscription(
#     config: FromDishka[AppConfig],
#     user_dao: FromDishka[UserDao],
#     reissue_subscription: FromDishka[ReissueSubscription],
#     authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
# ) -> ReissueResponse:
#     user = await _get_user_from_auth_header(authorization, user_dao, config)
#     await reissue_subscription(user)
#     return ReissueResponse(success=True)


@router.post("/subscription/purchase", response_model=PaymentInitResponse)
@inject
async def purchase_subscription(
    body: PurchaseRequest,
    config: FromDishka[AppConfig],
    uow: FromDishka[UnitOfWork],
    user_dao: FromDishka[UserDao],
    subscription_dao: FromDishka[SubscriptionDao],
    transaction_dao: FromDishka[TransactionDao],
    payment_gateway_dao: FromDishka[PaymentGatewayDao],
    pricing_service: FromDishka[PricingService],
    get_available_plans: FromDishka[GetAvailablePlans],
    create_payment: FromDishka[CreatePayment],
    remnawave: FromDishka[Remnawave],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> PaymentInitResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    _assert_web_purchase_email_verified(user)
    await _validate_gateway_for_web(body.gateway_type, payment_gateway_dao)

    plan = await _get_available_plan_by_code(user, body.plan_code, get_available_plans)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    duration = plan.get_duration(body.duration_days)
    if not duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan duration not found",
        )

    gateway = await payment_gateway_dao.get_by_type(body.gateway_type)
    if not gateway:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway not found")

    current_subscription = await subscription_dao.get_current(user.telegram_id)
    purchase_type = PurchaseType.CHANGE if current_subscription else PurchaseType.NEW
    plan_snapshot = PlanSnapshotDto.from_plan(plan, duration.days)
    pricing = pricing_service.calculate(
        user,
        duration.get_price(gateway.currency),
        gateway.currency,
    )

    payment = await create_payment(
        user,
        CreatePaymentDto(
            plan_snapshot=plan_snapshot,
            pricing=pricing,
            purchase_type=purchase_type,
            gateway_type=body.gateway_type,
        ),
    )

    tx_status = TransactionStatus.PENDING
    if pricing.is_free:
        await _complete_free_purchase(
            user=user,
            payment_id=str(payment.id),
            uow=uow,
            transaction_dao=transaction_dao,
            subscription_dao=subscription_dao,
            user_dao=user_dao,
            remnawave=remnawave,
        )
        tx_status = TransactionStatus.COMPLETED

    return PaymentInitResponse(
        payment_id=str(payment.id),
        payment_url=payment.url,
        purchase_type=purchase_type.value,
        status=tx_status.value,
        is_free=pricing.is_free,
        final_amount=str(pricing.final_amount),
        currency=gateway.currency.symbol,
    )


@router.post("/subscription/extend", response_model=PaymentInitResponse)
@inject
async def extend_subscription(
    body: ExtendRequest,
    config: FromDishka[AppConfig],
    uow: FromDishka[UnitOfWork],
    user_dao: FromDishka[UserDao],
    subscription_dao: FromDishka[SubscriptionDao],
    transaction_dao: FromDishka[TransactionDao],
    payment_gateway_dao: FromDishka[PaymentGatewayDao],
    pricing_service: FromDishka[PricingService],
    get_available_plans: FromDishka[GetAvailablePlans],
    match_plan: FromDishka[MatchPlan],
    create_payment: FromDishka[CreatePayment],
    remnawave: FromDishka[Remnawave],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> PaymentInitResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    _assert_web_purchase_email_verified(user)
    await _validate_gateway_for_web(body.gateway_type, payment_gateway_dao)

    current_subscription = await subscription_dao.get_current(user.telegram_id)
    if not current_subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    available_plans = await get_available_plans.system(user)
    matched_plan = await match_plan.system(
        MatchPlanDto(plan_snapshot=current_subscription.plan_snapshot, plans=available_plans)
    )
    if not matched_plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Matching plan for renewal is not available",
        )

    duration = matched_plan.get_duration(body.duration_days)
    if not duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan duration not found",
        )

    gateway = await payment_gateway_dao.get_by_type(body.gateway_type)
    if not gateway:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway not found")

    pricing = pricing_service.calculate(
        user,
        duration.get_price(gateway.currency),
        gateway.currency,
    )
    plan_snapshot = PlanSnapshotDto.from_plan(matched_plan, duration.days)
    payment = await create_payment(
        user,
        CreatePaymentDto(
            plan_snapshot=plan_snapshot,
            pricing=pricing,
            purchase_type=PurchaseType.RENEW,
            gateway_type=body.gateway_type,
        ),
    )

    tx_status = TransactionStatus.PENDING
    if pricing.is_free:
        await _complete_free_purchase(
            user=user,
            payment_id=str(payment.id),
            uow=uow,
            transaction_dao=transaction_dao,
            subscription_dao=subscription_dao,
            user_dao=user_dao,
            remnawave=remnawave,
        )
        tx_status = TransactionStatus.COMPLETED

    return PaymentInitResponse(
        payment_id=str(payment.id),
        payment_url=payment.url,
        purchase_type=PurchaseType.RENEW.value,
        status=tx_status.value,
        is_free=pricing.is_free,
        final_amount=str(pricing.final_amount),
        currency=gateway.currency.symbol,
    )


@router.get("/referral/program", response_model=ReferralProgramResponse)
@inject
async def get_referral_program(
    config: FromDishka[AppConfig],
    user_dao: FromDishka[UserDao],
    settings_dao: FromDishka[SettingsDao],
    referral_dao: FromDishka[ReferralDao],
    subscription_dao: FromDishka[SubscriptionDao],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> ReferralProgramResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Referral program is available only for users with verified email",
        )

    current_subscription = await subscription_dao.get_current(user.telegram_id)
    if not current_subscription or current_subscription.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Referral program is available only for users with active subscription",
        )

    settings = await settings_dao.get()

    invited_count = await referral_dao.get_referrals_count(user.telegram_id)
    invited_with_payment_count = await referral_dao.get_referrals_with_payment_count(
        user.telegram_id
    )

    reward_levels = [
        ReferralRewardLevelResponse(level=level.value, value=value)
        for level, value in sorted(
            settings.referral.reward.config.items(),
            key=lambda item: item[0].value,
        )
        if level.value <= settings.referral.level.value
    ]

    return ReferralProgramResponse(
        enabled=settings.referral.enable,
        referral_code=user.referral_code,
        invited_count=invited_count,
        invited_with_payment_count=invited_with_payment_count,
        reward_type=settings.referral.reward.type.value,
        reward_strategy=settings.referral.reward.strategy.value,
        accrual_strategy=settings.referral.accrual_strategy.value,
        max_level=settings.referral.level.value,
        reward_levels=reward_levels,
    )


@router.get("/subscription/offers", response_model=SubscriptionOffersResponse)
@inject
async def get_subscription_offers(
    config: FromDishka[AppConfig],
    user_dao: FromDishka[UserDao],
    subscription_dao: FromDishka[SubscriptionDao],
    payment_gateway_dao: FromDishka[PaymentGatewayDao],
    pricing_service: FromDishka[PricingService],
    get_available_plans: FromDishka[GetAvailablePlans],
    match_plan: FromDishka[MatchPlan],
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> SubscriptionOffersResponse:
    user = await _get_user_from_auth_header(authorization, user_dao, config)

    active_gateways = await payment_gateway_dao.get_active()
    web_gateways = [
        gateway
        for gateway in active_gateways
        if gateway.type != PaymentGatewayType.TELEGRAM_STARS
        and gateway.settings
        and gateway.settings.is_configured
    ]

    available_plans = await get_available_plans.system(user)
    current_subscription = await subscription_dao.get_current(user.telegram_id)

    matched_plan: Optional[PlanDto] = None
    if current_subscription:
        matched_plan = await match_plan.system(
            MatchPlanDto(
                plan_snapshot=current_subscription.plan_snapshot,
                plans=available_plans,
            )
        )

    plan_offers: list[PlanOfferResponse] = []
    for plan in available_plans:
        if not plan.public_code:
            continue

        duration_offers: list[DurationOfferResponse] = []
        for duration in plan.durations:
            prices: list[DurationGatewayPriceResponse] = []
            for gateway in web_gateways:
                pricing = pricing_service.calculate(
                    user=user,
                    price=duration.get_price(gateway.currency),
                    currency=gateway.currency,
                )
                prices.append(
                    DurationGatewayPriceResponse(
                        gateway_type=gateway.type,
                        currency=gateway.currency.value,
                        currency_symbol=gateway.currency.symbol,
                        original_amount=str(pricing.original_amount),
                        discount_percent=pricing.discount_percent,
                        final_amount=str(pricing.final_amount),
                        is_free=pricing.is_free,
                    )
                )

            duration_offers.append(DurationOfferResponse(days=duration.days, prices=prices))

        is_renew_candidate = (
            current_subscription is not None
            and matched_plan is not None
            and matched_plan.id == plan.id
            and not current_subscription.is_unlimited
        )
        recommended_purchase_type = (
            PurchaseType.RENEW.value
            if is_renew_candidate
            else (PurchaseType.CHANGE.value if current_subscription else PurchaseType.NEW.value)
        )

        plan_offers.append(
            PlanOfferResponse(
                id=plan.id,  # type: ignore[arg-type]
                public_code=plan.public_code,
                name=plan.name,
                description=plan.description,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                type=plan.type.value,
                recommended_purchase_type=recommended_purchase_type,
                durations=duration_offers,
            )
        )

    gateway_offers = [
        GatewayOfferResponse(
            gateway_type=gateway.type,
            currency=gateway.currency.value,
            currency_symbol=gateway.currency.symbol,
        )
        for gateway in web_gateways
    ]

    return SubscriptionOffersResponse(
        gateways=gateway_offers,
        plans=plan_offers,
        has_current_subscription=bool(current_subscription),
        current_subscription_status=(
            current_subscription.current_status.value if current_subscription else None
        ),
    )
