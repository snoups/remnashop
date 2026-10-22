from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import LegalDocumentKind, PurchaseChannel
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways import GatewayRepository
from app.modules.legal.dto import LegalDocumentsDto
from app.modules.legal.repository import LegalRepository
from app.modules.legal.visibility import visible_documents
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationRepository


class ListLegalDocumentsUseCase(UseCase[None, LegalDocumentsDto]):
    required_permission = Permission.LEGAL_DOCUMENTS_VIEW

    def __init__(
        self,
        legal_repository: LegalRepository,
        gateway_repository: GatewayRepository,
        settings_repository: SettingsRepository,
        translation_repository: TranslationRepository,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._gateway_repository = gateway_repository
        self._settings_repository = settings_repository
        self._translation_repository = translation_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> LegalDocumentsDto:
        async with self._uow:
            documents = await self._legal_repository.list_documents()
            requests = await self._legal_repository.list_reacceptance_requests()
            texts = [
                text.model_copy(
                    update={
                        "last_reacceptance_at": requests.get((text.kind, text.locale, text.channel))
                    }
                )
                for text in await self._legal_repository.list_current_revisions()
                if text.body.strip()
            ]
            locales = await self._translation_repository.list_active_locales()
            default_locale = await self._translation_repository.get_default_locale()
            can_pay = any(
                gateway.is_active and gateway.is_configured
                for gateway in await self._gateway_repository.get_all()
            )
            bot_ready = (await self._settings_repository.get_bot_settings()).is_configured
            channels = {
                PurchaseChannel.BOT: bot_ready,
                PurchaseChannel.CABINET: bool(self._config.cabinet.url),
            }
            missing: list[PurchaseChannel] = []
            for channel, ready in channels.items():
                if not (can_pay and ready):
                    continue
                shown = await visible_documents(
                    self._legal_repository,
                    documents,
                    channel,
                    default_locale,
                    default_locale,
                    locales,
                )
                if all(revision.kind != LegalDocumentKind.OFFER for revision in shown):
                    missing.append(channel)
        return LegalDocumentsDto(
            documents=documents, texts=texts, offer_missing_in=missing, locales=locales
        )
