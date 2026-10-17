from typing import Optional

from app.core.constants import TTL_10M
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.ports import EventPublisher
from app.core.utils.email import normalize_email
from app.modules.account_merge import CustomerAccountMerger
from app.modules.blacklist import BlacklistRepository
from app.modules.cabinet_auth import is_allowed_domain
from app.modules.identity_links.dto import (
    IdentityClaimDto,
    IdentityKind,
    LinkResultDto,
    MergePreviewDto,
)
from app.modules.identity_links.events import SignInMethodLinkedEvent
from app.modules.identity_links.identities import build_identities
from app.modules.identity_links.merge_tokens import MergeTokenStore
from app.modules.oauth import CreateOAuthIdentityDto, OAuthIdentityRepository, OAuthProfile
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto, UserRepository


def _blacklisted() -> PermissionDeniedError:
    return PermissionDeniedError(
        "This sign-in method is blacklisted", code=ErrorCode.IDENTITY_BLACKLISTED
    )


class IdentityLinker:
    def __init__(
        self,
        user_repository: UserRepository,
        oauth_identity_repository: OAuthIdentityRepository,
        blacklist_repository: BlacklistRepository,
        settings_repository: SettingsRepository,
        merger: CustomerAccountMerger,
        merge_tokens: MergeTokenStore,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._oauth_identity_repository = oauth_identity_repository
        self._blacklist_repository = blacklist_repository
        self._settings_repository = settings_repository
        self._merger = merger
        self._merge_tokens = merge_tokens
        self._event_publisher = event_publisher
        self._uow = uow

    async def owner_of(self, claim: IdentityClaimDto) -> Optional[int]:
        if claim.kind is IdentityKind.TELEGRAM:
            assert claim.telegram is not None
            user = await self._user_repository.get_by_telegram_id(claim.telegram.telegram_id)
            return user.id if user else None
        if claim.kind is IdentityKind.EMAIL:
            assert claim.email is not None
            user = await self._user_repository.get_by_email(normalize_email(claim.email))
            return user.id if user else None
        assert claim.oauth is not None
        identity = await self._oauth_identity_repository.get_by_provider_external_id(
            OAuthProvider(claim.kind.value), claim.oauth.external_id
        )
        return identity.user_id if identity else None

    async def link(self, user: UserDto, claim: IdentityClaimDto, client_ip: str) -> LinkResultDto:
        async with self._uow:
            owner_id = await self.owner_of(claim)
            if owner_id == user.id:
                return LinkResultDto(status="already_linked")
            # locked: two links of the same kind at once can't both fill the slot
            fresh = await self._user_repository.find_live_for_update(user.id)
            if fresh is None:
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            await self._ensure_slot_free(fresh, claim.kind)
            if owner_id is None:
                await self._attach(fresh, claim)
                await self._event_publisher.publish(
                    SignInMethodLinkedEvent(user=fresh, kind=claim.kind, ip_address=client_ip)
                )
                return LinkResultDto(status="linked")

        counts = await self._merger.check(user, owner_id)
        async with self._uow:
            other = await self._user_repository.find_by_id(owner_id)
            if other is None:
                # merged away or deleted since owner_of read it
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            oauth_identities = await self._oauth_identity_repository.list_by_user(owner_id)
        identities = build_identities(other, cabinet, oauth_identities)
        token = await self._merge_tokens.issue(user.id, owner_id, claim)
        return LinkResultDto(
            status="merge_required",
            merge_token=token,
            expires_in=TTL_10M,
            other=MergePreviewDto(
                subscriptions=counts.subscriptions,
                transactions=counts.transactions,
                referrals=counts.referrals,
                identities=[identity for identity in identities if identity.linked],
            ),
        )

    async def _ensure_slot_free(self, user: UserDto, kind: IdentityKind) -> None:
        if kind is IdentityKind.TELEGRAM:
            taken = user.telegram_id is not None
        elif kind is IdentityKind.EMAIL:
            taken = user.email is not None
        else:
            provider = OAuthProvider(kind.value)
            identities = await self._oauth_identity_repository.list_by_user(user.id)
            taken = any(identity.provider is provider for identity in identities)
        if taken:
            raise ConflictError(
                f"A different '{kind.value.lower()}' is already linked",
                code=ErrorCode.MERGE_IDENTITY_CONFLICT,
            )

    async def _attach(self, user: UserDto, claim: IdentityClaimDto) -> None:
        if claim.kind is IdentityKind.EMAIL:
            assert claim.email is not None
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            if not is_allowed_domain(claim.email, cabinet):
                raise ValidationError(
                    "Email domain is not allowed", code=ErrorCode.EMAIL_DOMAIN_NOT_ALLOWED
                )
            if await self._blacklist_repository.is_blacklisted_email(claim.email):
                raise _blacklisted()
            await self._user_repository.set_email(user.id, claim.email)
        elif claim.kind is IdentityKind.TELEGRAM:
            profile = claim.telegram
            assert profile is not None
            if await self._blacklist_repository.is_blacklisted_telegram_id(profile.telegram_id):
                raise _blacklisted()
            await self._user_repository.set_telegram_id(user.id, profile.telegram_id)
            if profile.username:
                # set_telegram_id drops the username; the account keeps its own name and language
                await self._user_repository.update_telegram_profile(
                    user.id, name=user.name, username=profile.username, language=user.language
                )
        else:
            assert claim.oauth is not None
            await self._oauth_identity_repository.create(
                CreateOAuthIdentityDto(
                    user_id=user.id,
                    provider=OAuthProvider(claim.kind.value),
                    external_id=claim.oauth.external_id,
                    external_login=claim.oauth.login,
                )
            )
            await self._adopt_provider_email(user, claim.oauth)

    async def _adopt_provider_email(self, user: UserDto, profile: OAuthProfile) -> None:
        # a proven address fills an empty slot; someone else's is ignored, never merged
        if user.email is not None or not profile.email or not profile.email_verified:
            return
        email = normalize_email(profile.email)
        if await self._user_repository.get_by_email(email) is not None:
            return
        if await self._blacklist_repository.is_blacklisted_email(email):
            return
        await self._user_repository.set_email(user.id, email)
