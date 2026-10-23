from typing import Final, Optional

from app.core.constants import TTL_30D
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AccessDenial,
    AdLinkChannel,
    CabinetSignInMethod,
    LegalAcceptanceTrigger,
    LegalDocumentKind,
    Locale,
    OAuthProvider,
    PurchaseChannel,
    RegistrationSource,
    SessionAudience,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.utils.email import normalize_email
from app.core.utils.http import describe_user_agent
from app.modules.access import CheckRegistrationAccessDto, CheckRegistrationAccessUseCase
from app.modules.auth import IssuedSession, SessionIssuer
from app.modules.blacklist import BlacklistRepository
from app.modules.cabinet_auth.devices import KnownDevices
from app.modules.cabinet_auth.dto import InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.email_domains import is_allowed_domain
from app.modules.cabinet_auth.events import CabinetNewDeviceSignInEvent, CabinetSignedInEvent
from app.modules.legal import LegalAcceptanceRecorder
from app.modules.oauth import CreateOAuthIdentityDto, OAuthIdentityRepository, OAuthProfile
from app.modules.settings import SettingsRepository
from app.modules.users import (
    RegisterCabinetUserDto,
    RegisterCabinetUserUseCase,
    RegisterTelegramUserDto,
    RegisterTelegramUserUseCase,
    RegistrationSnapshotDto,
    UserDto,
    UserRepository,
)

_SIGN_UP_DOCUMENTS: Final[frozenset[LegalDocumentKind]] = frozenset(
    {LegalDocumentKind.USER_AGREEMENT, LegalDocumentKind.PRIVACY_POLICY}
)

_DENIAL_ERRORS: Final[dict[AccessDenial, ErrorCode]] = {
    AccessDenial.RESTRICTED: ErrorCode.ACCESS_RESTRICTED,
    AccessDenial.REGISTRATION_DISABLED: ErrorCode.REGISTRATION_CLOSED,
    AccessDenial.INVITE_ONLY: ErrorCode.REGISTRATION_INVITE_ONLY,
}


def _parse_locale(code: Optional[str]) -> Optional[Locale]:
    try:
        return Locale(code[:2].lower()) if code else None
    except ValueError:
        return None


def telegram_profile_from_oauth(profile: OAuthProfile) -> TelegramProfileDto:
    # Telegram OIDC: the subject is the telegram_id
    return TelegramProfileDto(
        telegram_id=int(profile.external_id),
        name=profile.name or profile.login or "",
        username=profile.login,
        language=profile.language,
    )


class CabinetSignIn:
    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        settings_repository: SettingsRepository,
        oauth_identity_repository: OAuthIdentityRepository,
        register_telegram_user_use_case: RegisterTelegramUserUseCase,
        register_cabinet_user_use_case: RegisterCabinetUserUseCase,
        check_registration_access_use_case: CheckRegistrationAccessUseCase,
        session_issuer: SessionIssuer,
        known_devices: KnownDevices,
        legal_acceptance_recorder: LegalAcceptanceRecorder,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._settings_repository = settings_repository
        self._oauth_identity_repository = oauth_identity_repository
        self._register_telegram_user_use_case = register_telegram_user_use_case
        self._register_cabinet_user_use_case = register_cabinet_user_use_case
        self._check_registration_access_use_case = check_registration_access_use_case
        self._session_issuer = session_issuer
        self._known_devices = known_devices
        self._legal_acceptance_recorder = legal_acceptance_recorder
        self._event_publisher = event_publisher
        self._uow = uow

    async def ensure_can_register(
        self,
        codes: InviteCodesDto,
        *,
        telegram_id: Optional[int] = None,
        email: Optional[str] = None,
    ) -> None:
        # passes existing users through, so it's safe to call before a lookup
        denial = await self._check_registration_access_use_case.system(
            CheckRegistrationAccessDto(
                channel=AdLinkChannel.WEBCABINET,
                telegram_id=telegram_id,
                email=email,
                referral_code=codes.referral_code,
                ad_link_code=codes.ad_link_code,
            )
        )
        if denial is not None:
            raise PermissionDeniedError(
                "Registration is not available", code=_DENIAL_ERRORS[denial]
            )

    async def issue_for(
        self,
        user: UserDto,
        client_ip: str,
        user_agent: Optional[str],
        method: CabinetSignInMethod,
        session_ttl: int = TTL_30D,
        legal_locale: Optional[Locale] = None,
    ) -> tuple[UserDto, IssuedSession]:
        if user.is_blocked:
            raise PermissionDeniedError("User is blocked", code=ErrorCode.USER_BLOCKED)
        issued = await self._session_issuer.issue(
            user.id,
            client_ip,
            user_agent,
            audience=SessionAudience.CABINET,
            ttl_seconds=session_ttl,
        )
        try:
            await self._record_sign_in(user, method, client_ip, legal_locale)
        except BaseException:
            # the browser never gets this session's cookies: don't leave it active
            await self._session_issuer.revoke(issued.session_id)
            raise
        # after the commit: a device noted for a sign-in that rolled back would
        # silence the alert for the real one
        if await self._known_devices.remember(user.id, client_ip, user_agent):
            async with self._uow:
                await self._event_publisher.publish(
                    CabinetNewDeviceSignInEvent(
                        user=user,
                        browser=describe_user_agent(user_agent),
                        ip_address=client_ip,
                    )
                )
        return user, issued

    async def _record_sign_in(
        self,
        user: UserDto,
        method: CabinetSignInMethod,
        client_ip: str,
        legal_locale: Optional[Locale],
    ) -> None:
        async with self._uow:
            if legal_locale is not None and not await self._legal_acceptance_recorder.has_signed_up(
                user.id, PurchaseChannel.CABINET
            ):
                await self._legal_acceptance_recorder.record(
                    user_id=user.id,
                    channel=PurchaseChannel.CABINET,
                    trigger=LegalAcceptanceTrigger.SIGN_UP,
                    locale=legal_locale,
                    kinds=_SIGN_UP_DOCUMENTS,
                    ip_address=client_ip,
                )
            await self._event_publisher.publish(
                CabinetSignedInEvent(user=user, method=method, ip_address=client_ip)
            )

    async def telegram(
        self,
        profile: TelegramProfileDto,
        codes: InviteCodesDto,
        client_ip: str,
        user_agent: Optional[str],
        session_ttl: int = TTL_30D,
        source: RegistrationSource = RegistrationSource.CABINET_TELEGRAM,
        legal_locale: Optional[Locale] = None,
    ) -> tuple[UserDto, IssuedSession]:
        # blacklisted: the register usecase stores a blocked row, issue_for refuses it
        async with self._uow:
            blacklisted = await self._blacklist_repository.is_blacklisted_telegram_id(
                profile.telegram_id
            )
        if not blacklisted:
            await self.ensure_can_register(codes, telegram_id=profile.telegram_id)
        language = _parse_locale(profile.language)
        user = await self._register_telegram_user_use_case.system(
            RegisterTelegramUserDto(
                telegram_id=profile.telegram_id,
                name=profile.name,
                username=profile.username,
                # no TranslatorHub default in the api process; the client changes it later
                language=language or Locale.EN,
                sync_language=language is not None,
                channel=AdLinkChannel.WEBCABINET,
                ad_link_code=codes.ad_link_code,
                referral_code=codes.referral_code,
                snapshot=RegistrationSnapshotDto(
                    source=source,
                    telegram_language_code=profile.language,
                    ip_address=client_ip,
                    user_agent=user_agent,
                ),
            )
        )
        return await self.issue_for(
            user,
            client_ip,
            user_agent,
            CabinetSignInMethod.TELEGRAM,
            session_ttl,
            legal_locale,
        )

    async def email(
        self,
        email: str,
        language: Locale,
        codes: InviteCodesDto,
        client_ip: str,
        user_agent: Optional[str],
        legal_locale: Optional[Locale] = None,
    ) -> tuple[UserDto, IssuedSession]:
        email = normalize_email(email)
        async with self._uow:
            user = await self._user_repository.get_by_email(email)
        if user is None:
            async with self._uow:
                cabinet = await self._settings_repository.get_cabinet_auth_settings()
            if not is_allowed_domain(email, cabinet):
                raise ValidationError(
                    "Email domain is not allowed", code=ErrorCode.EMAIL_DOMAIN_NOT_ALLOWED
                )
            async with self._uow:
                blacklisted = await self._blacklist_repository.is_blacklisted_email(email)
            if not blacklisted:
                await self.ensure_can_register(codes, email=email)
            user = await self._register_cabinet_user_use_case.system(
                RegisterCabinetUserDto(
                    name=email.split("@", 1)[0],
                    language=language,
                    method=CabinetSignInMethod.EMAIL,
                    email=email,
                    ad_link_code=codes.ad_link_code,
                    referral_code=codes.referral_code,
                    snapshot=RegistrationSnapshotDto(
                        source=RegistrationSource.CABINET_EMAIL,
                        ip_address=client_ip,
                        user_agent=user_agent,
                    ),
                )
            )
        elif user.email_undeliverable_at is not None:
            # a received sign-in code proves the address works again
            async with self._uow:
                await self._user_repository.set_email_undeliverable(user.id, None)
        return await self.issue_for(
            user, client_ip, user_agent, CabinetSignInMethod.EMAIL, legal_locale=legal_locale
        )

    async def _user_by_verified_email(self, verified_email: str) -> Optional[UserDto]:
        async with self._uow:
            user = await self._user_repository.get_by_email(verified_email)
        # matched only canonically (an alias): on a host where "+" is part of the
        # name that is another person's mailbox, so the provider proves nothing here
        if user is not None and normalize_email(user.email or "") != verified_email:
            raise ConflictError("Email already in use", code=ErrorCode.EMAIL_TAKEN)
        return user

    async def oauth(
        self,
        provider: OAuthProvider,
        profile: OAuthProfile,
        codes: InviteCodesDto,
        client_ip: str,
        user_agent: Optional[str],
        legal_locale: Optional[Locale] = None,
    ) -> tuple[UserDto, IssuedSession]:
        if provider is OAuthProvider.TELEGRAM:
            return await self.telegram(
                telegram_profile_from_oauth(profile),
                codes,
                client_ip,
                user_agent,
                legal_locale=legal_locale,
            )
        user = await self._user_by_identity(provider, profile.external_id)
        if user is not None:
            return await self.issue_for(
                user,
                client_ip,
                user_agent,
                CabinetSignInMethod(provider.value),
                legal_locale=legal_locale,
            )

        # users.email holds only proven addresses
        verified_email = (
            normalize_email(profile.email) if profile.email and profile.email_verified else None
        )
        if verified_email:
            user = await self._user_by_verified_email(verified_email)
        if user is None:
            if verified_email:
                async with self._uow:
                    blacklisted = await self._blacklist_repository.is_blacklisted_email(
                        verified_email
                    )
                if not blacklisted:
                    await self.ensure_can_register(codes, email=verified_email)
            else:
                await self.ensure_can_register(codes)
            user = await self._register_cabinet_user_use_case.system(
                RegisterCabinetUserDto(
                    name=profile.name or profile.login or provider.value.title(),
                    language=_parse_locale(profile.language) or Locale.EN,
                    method=CabinetSignInMethod(provider.value),
                    email=verified_email,
                    ad_link_code=codes.ad_link_code,
                    referral_code=codes.referral_code,
                    snapshot=RegistrationSnapshotDto(
                        source=RegistrationSource(f"CABINET_{provider.value}"),
                        ip_address=client_ip,
                        user_agent=user_agent,
                    ),
                )
            )
        user = await self._link_identity(user, provider, profile)
        return await self.issue_for(
            user,
            client_ip,
            user_agent,
            CabinetSignInMethod(provider.value),
            legal_locale=legal_locale,
        )

    async def _link_identity(
        self, user: UserDto, provider: OAuthProvider, profile: OAuthProfile
    ) -> UserDto:
        """The account the provider identity ends up on."""
        # refused before a link is made: a blocked account must not gain a sign-in method
        if user.is_blocked:
            raise PermissionDeniedError("User is blocked", code=ErrorCode.USER_BLOCKED)
        async with self._uow:
            linked = await self._oauth_identity_repository.list_by_user(user.id)
        if any(identity.provider is provider for identity in linked):
            # another account of this provider is already linked: sign in, keep the link
            return user
        try:
            async with self._uow:
                await self._oauth_identity_repository.create(
                    CreateOAuthIdentityDto(
                        user_id=user.id,
                        provider=provider,
                        external_id=profile.external_id,
                        external_login=profile.login,
                    )
                )
        except ConflictError:
            # a concurrent sign-in with the same account linked it first
            winner = await self._user_by_identity(provider, profile.external_id)
            if winner is None:
                raise
            return winner
        return user

    async def _user_by_identity(
        self, provider: OAuthProvider, external_id: str
    ) -> Optional[UserDto]:
        async with self._uow:
            identity = await self._oauth_identity_repository.get_by_provider_external_id(
                provider, external_id
            )
            return await self._user_repository.find_by_id(identity.user_id) if identity else None
