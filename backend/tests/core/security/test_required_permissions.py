import pytest

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.usecases.get_ad_link import GetAdLinkUseCase
from app.modules.banners.usecases.delete_banner import DeleteBannerUseCase
from app.modules.banners.usecases.get_banner_image import GetBannerImageUseCase
from app.modules.banners.usecases.upload_banner import UploadBannerUseCase
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
from app.modules.gateways.usecases.list_gateways import ListGatewaysUseCase
from app.modules.gateways.usecases.reorder_gateways import ReorderGatewaysUseCase
from app.modules.gateways.usecases.set_gateway_active import SetGatewayActiveUseCase
from app.modules.gateways.usecases.update_gateway_settings import UpdateGatewaySettingsUseCase
from app.modules.plans.usecases import GetAddOnUseCase
from app.modules.plans.usecases.get_plan import GetPlanUseCase
from app.modules.plans.usecases.set_plan_duration_base_price import SetPlanDurationBasePriceUseCase
from app.modules.promocodes.usecases.get_promocode import GetPromocodeUseCase
from app.modules.settings.usecases.get_bot_commands import GetBotCommandsUseCase
from app.modules.subscriptions.usecases.get_subscription import GetSubscriptionUseCase
from app.modules.transactions.usecases.create_test_payment import CreateTestPaymentUseCase
from app.modules.transactions.usecases.fulfill_transaction import FulfillTransactionUseCase
from app.modules.transactions.usecases.get_test_payment_status import GetTestPaymentStatusUseCase
from app.modules.transactions.usecases.get_transaction import GetTransactionUseCase
from app.modules.transactions.usecases.list_transaction_gateways import (
    ListTransactionGatewaysUseCase,
)
from app.modules.transactions.usecases.list_transactions import ListTransactionsUseCase
from app.modules.translations.usecases.add_locale import AddLocaleUseCase
from app.modules.translations.usecases.remove_locale import RemoveLocaleUseCase
from app.modules.translations.usecases.reset_translation import ResetTranslationUseCase
from app.modules.translations.usecases.update_translation import UpdateTranslationUseCase
from app.modules.users.usecases.get_user import GetUserUseCase
from app.modules.users.usecases.set_user_discount import SetUserDiscountUseCase


@pytest.mark.parametrize(
    ("usecase_class", "expected_permission"),
    [
        (GetUserUseCase, Permission.USERS_DETAIL_VIEW),
        (GetAdLinkUseCase, Permission.AD_LINKS_DETAIL_VIEW),
        (GetEventLogEntryUseCase, Permission.EVENT_LOG_DETAIL_VIEW),
        (GetPromocodeUseCase, Permission.PROMOCODES_DETAIL_VIEW),
        (GetSubscriptionUseCase, Permission.SUBSCRIPTIONS_DETAIL_VIEW),
        (GetAddOnUseCase, Permission.ADDONS_DETAIL_VIEW),
        (GetPlanUseCase, Permission.PLANS_DETAIL_VIEW),
        (UploadBannerUseCase, Permission.BANNERS_UPLOAD),
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
