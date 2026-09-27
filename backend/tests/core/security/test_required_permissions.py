import pytest

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
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
from app.modules.gateways.usecases.list_gateways import ListGatewaysUseCase
from app.modules.gateways.usecases.reorder_gateways import ReorderGatewaysUseCase
from app.modules.gateways.usecases.toggle_gateway_active import ToggleGatewayActiveUseCase
from app.modules.gateways.usecases.update_gateway_settings import UpdateGatewaySettingsUseCase
from app.modules.payments.usecases.create_test_payment import CreateTestPaymentUseCase
from app.modules.payments.usecases.get_payment_order import GetPaymentOrderUseCase
from app.modules.payments.usecases.get_test_payment_status import GetTestPaymentStatusUseCase
from app.modules.payments.usecases.list_payment_order_gateways import (
    ListPaymentOrderGatewaysUseCase,
)
from app.modules.payments.usecases.list_payment_orders import ListPaymentOrdersUseCase
from app.modules.plans.usecases.set_plan_duration_base_price import (
    SetPlanDurationBasePriceUseCase,
)
from app.modules.settings.usecases.add_locale import AddLocaleUseCase
from app.modules.settings.usecases.get_bot_commands import GetBotCommandsUseCase
from app.modules.settings.usecases.remove_locale import RemoveLocaleUseCase
from app.modules.translations.usecases.reset_translation import ResetTranslationUseCase
from app.modules.translations.usecases.update_translation import UpdateTranslationUseCase
from app.modules.users.usecases.set_user_personal_discount import (
    SetUserPersonalDiscountUseCase,
)


@pytest.mark.parametrize(
    ("usecase_class", "expected_permission"),
    [
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
        (ToggleGatewayActiveUseCase, Permission.GATEWAYS_TOGGLE),
        (ReorderGatewaysUseCase, Permission.GATEWAYS_REORDER),
        (CreateTestPaymentUseCase, Permission.GATEWAYS_TEST),
        (GetTestPaymentStatusUseCase, Permission.GATEWAYS_TEST_VIEW),
        (SetUserPersonalDiscountUseCase, Permission.USERS_DISCOUNT_MANAGE),
        (ListPaymentOrdersUseCase, Permission.PAYMENTS_VIEW),
        (ListPaymentOrderGatewaysUseCase, Permission.PAYMENTS_GATEWAYS_VIEW),
        (GetPaymentOrderUseCase, Permission.PAYMENTS_ORDER_VIEW),
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
