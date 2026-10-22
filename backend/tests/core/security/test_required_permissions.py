import pytest

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.usecases import GetAdLinkUseCase
from app.modules.banners.usecases import (
    DeleteBannerUseCase,
    GetBannerImageUseCase,
    UploadBannerUseCase,
)
from app.modules.dialogs.usecases import (
    CreateCustomDialogWindowUseCase,
    DeleteCustomDialogWindowUseCase,
    GetDialogCatalogUseCase,
    ListDialogWindowsUseCase,
    ResetAllDialogsUseCase,
    ResetDialogWindowUseCase,
    UpdateDialogTextUseCase,
    UpdateDialogWindowButtonsUseCase,
    UpdateDialogWindowUseCase,
)
from app.modules.event_log.usecases import GetEventLogEntryUseCase
from app.modules.gateways.usecases import (
    ListGatewaysUseCase,
    ReorderGatewaysUseCase,
    SetGatewayActiveUseCase,
    UpdateGatewaySettingsUseCase,
)
from app.modules.legal.usecases import (
    ListLegalDocumentsUseCase,
    ListUserLegalAcceptancesUseCase,
    RemoveLegalTextUseCase,
    SetLegalTextUseCase,
    UpdateLegalDocumentUseCase,
)
from app.modules.notifications.usecases import (
    GenerateVapidKeysUseCase,
    GetNotificationSettingsUseCase,
    UpdateNotificationSettingsUseCase,
)
from app.modules.plans.usecases import (
    GetAddOnUseCase,
    GetPlanUseCase,
    SetPlanDurationBasePriceUseCase,
)
from app.modules.promocodes.usecases import GetPromocodeUseCase
from app.modules.settings.usecases import GetBotCommandsUseCase
from app.modules.subscriptions.usecases import GetSubscriptionUseCase
from app.modules.transactions.usecases import (
    CreateTestPaymentUseCase,
    FulfillTransactionUseCase,
    GetTestPaymentStatusUseCase,
    GetTransactionUseCase,
    ListTransactionGatewaysUseCase,
    ListTransactionsUseCase,
)
from app.modules.translations.usecases import (
    AddLocaleUseCase,
    RemoveLocaleUseCase,
    ResetTranslationUseCase,
    UpdateTranslationUseCase,
)
from app.modules.users.usecases import GetUserUseCase, SetUserDiscountUseCase


@pytest.mark.parametrize(
    ("usecase_class", "expected_permission"),
    [
        (GetUserUseCase, Permission.USERS_DETAIL_VIEW),
        (GetAdLinkUseCase, Permission.AD_LINKS_DETAIL_VIEW),
        (GetEventLogEntryUseCase, Permission.EVENT_LOG_DETAIL_VIEW),
        (GetNotificationSettingsUseCase, Permission.NOTIFICATION_SETTINGS_VIEW),
        (UpdateNotificationSettingsUseCase, Permission.NOTIFICATION_SETTINGS_MANAGE),
        (GenerateVapidKeysUseCase, Permission.NOTIFICATION_VAPID_KEYS_GENERATE),
        (GetPromocodeUseCase, Permission.PROMOCODES_DETAIL_VIEW),
        (GetSubscriptionUseCase, Permission.SUBSCRIPTIONS_DETAIL_VIEW),
        (GetAddOnUseCase, Permission.ADDONS_DETAIL_VIEW),
        (GetPlanUseCase, Permission.PLANS_DETAIL_VIEW),
        (UploadBannerUseCase, Permission.BANNERS_UPLOAD),
        (ListLegalDocumentsUseCase, Permission.LEGAL_DOCUMENTS_VIEW),
        (UpdateLegalDocumentUseCase, Permission.LEGAL_DOCUMENTS_UPDATE),
        (SetLegalTextUseCase, Permission.LEGAL_TEXT_SET),
        (RemoveLegalTextUseCase, Permission.LEGAL_TEXT_REMOVE),
        (ListUserLegalAcceptancesUseCase, Permission.LEGAL_ACCEPTANCES_VIEW),
        (DeleteBannerUseCase, Permission.BANNERS_DELETE),
        (GetBannerImageUseCase, Permission.BANNERS_IMAGE_VIEW),
        (GetBotCommandsUseCase, Permission.BOT_COMMANDS_VIEW),
        (AddLocaleUseCase, Permission.LOCALES_ADD),
        (RemoveLocaleUseCase, Permission.LOCALES_REMOVE),
        (UpdateTranslationUseCase, Permission.TRANSLATIONS_UPDATE),
        (ResetTranslationUseCase, Permission.TRANSLATIONS_RESET),
        (ListGatewaysUseCase, Permission.GATEWAYS_VIEW),
        (UpdateGatewaySettingsUseCase, Permission.GATEWAYS_UPDATE),
        (SetGatewayActiveUseCase, Permission.GATEWAYS_ACTIVE_SET),
        (ReorderGatewaysUseCase, Permission.GATEWAYS_REORDER),
        (CreateTestPaymentUseCase, Permission.GATEWAYS_TEST),
        (GetTestPaymentStatusUseCase, Permission.GATEWAYS_TEST_VIEW),
        (SetUserDiscountUseCase, Permission.USERS_DISCOUNT_MANAGE),
        (ListTransactionsUseCase, Permission.TRANSACTIONS_VIEW),
        (ListTransactionGatewaysUseCase, Permission.TRANSACTIONS_GATEWAYS_VIEW),
        (GetTransactionUseCase, Permission.TRANSACTIONS_DETAIL_VIEW),
        (FulfillTransactionUseCase, Permission.TRANSACTIONS_FULFILL),
        (
            SetPlanDurationBasePriceUseCase,
            Permission.PLANS_DURATION_BASE_PRICE_MANAGE,
        ),
        (ListDialogWindowsUseCase, Permission.DIALOGS_WINDOWS_VIEW),
        (GetDialogCatalogUseCase, Permission.DIALOGS_CATALOG_VIEW),
        (UpdateDialogWindowUseCase, Permission.DIALOGS_WINDOWS_UPDATE),
        (UpdateDialogWindowButtonsUseCase, Permission.DIALOGS_WINDOWS_BUTTONS_UPDATE),
        (CreateCustomDialogWindowUseCase, Permission.DIALOGS_WINDOWS_CREATE),
        (DeleteCustomDialogWindowUseCase, Permission.DIALOGS_WINDOWS_DELETE),
        (ResetDialogWindowUseCase, Permission.DIALOGS_WINDOWS_RESET),
        (ResetAllDialogsUseCase, Permission.DIALOGS_WINDOWS_RESET_ALL),
        (UpdateDialogTextUseCase, Permission.DIALOGS_TEXT_UPDATE),
    ],
)
def test_split_usecase_requires_expected_permission(
    usecase_class: type[UseCase], expected_permission: Permission
) -> None:
    assert usecase_class.required_permission == expected_permission
